"""
Phase 4 — Candidate A backtest: cross-sectional monthly long/short in cash corporate
bonds, sorted on the frozen no-look-ahead dislocation signal, duration-matched
Treasury-hedged (credit-excess) returns as primary.

Design (user-approved; DESIGN ONLY was reviewed first):
  - Signal: Dislocation_{i,t} = eq_t - (alpha_t + beta_t * bd_t), with (alpha_t,beta_t)
    from the frozen expanding pooled regression on s<=t-1 (no look-ahead). Precomputed in
    signal_panel.parquet.
  - Formation: each signal month t, sort firms into QUINTILES by Dislocation_{i,t}.
    Deciles reported as robustness.
  - Long/short: LONG Q5 (equity outran bonds -> bond expected to catch up),
    SHORT Q1 (equity lagged -> bond expected to underperform). Dollar-neutral.
  - Weighting (TWO SEPARATE LAYERS):
      * within firm: AO-weighted bonds -> firm-level bond return (frozen Phase 2).
      * across firms (the portfolio): EQUAL-WEIGHT firms within each quintile (PRIMARY),
        so large debt issuers do not mechanically dominate. AO-across-firms (firm
        bond_ao_total) reported as a ROBUSTNESS portfolio only.
  - Return: firm credit-excess return bd_xs_{t+1} = corp bond ret - duration-matched
    Treasury ret (PRIMARY). Raw bond return bd_{t+1} as robustness (no hedge).
  - Hold 1 month, rebalance monthly.
  - Reported for ALL / HY (frac_ig_ao<0.5) / IG (>=0.5).
  - Metrics: ann. return, ann. vol, Sharpe, Newey-West t of monthly mean, hit rate,
    max drawdown, skew, turnover; gross first, then an ILLUSTRATIVE transaction-cost grid.

Transaction costs: `t_spread` is NOT used (its meaning is unverified; it is NOT a
confirmed bid-ask). All cost levels below are ILLUSTRATIVE ASSUMPTIONS, never estimates
of the true cost of trading these bonds.

Reads existing files only; writes NEW Phase-4 outputs. Does not re-extract or modify any
prior Phase 0-3 file.
Run: conda run -n credit-equity python -m src.backtest_candidateA
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json
from .rate_robustness import build_firm_rate_vars

log = get_logger()

N_QUANTILES_PRIMARY = 5          # quintiles
COST_GRID_BP = [0, 10, 25, 50, 100]   # ILLUSTRATIVE round-trip bp per name per rebalance
NW_LAGS = 3                      # Newey-West lags for the monthly mean t-stat


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def nw_tstat(x: np.ndarray, lags: int = NW_LAGS) -> float:
    """Newey-West t-stat for the mean of a monthly return series."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = x.size
    if n < 3:
        return np.nan
    mu = x.mean()
    e = x - mu
    gamma0 = (e @ e) / n
    var = gamma0
    for L in range(1, min(lags, n - 1) + 1):
        w = 1.0 - L / (lags + 1)
        cov = (e[L:] @ e[:-L]) / n
        var += 2.0 * w * cov
    se = np.sqrt(var / n)
    return float(mu / se) if se > 0 else np.nan


def max_drawdown(monthly: np.ndarray) -> float:
    """Max drawdown on the cumulative sum (returns are already excess/spread, additive)."""
    c = np.cumsum(np.asarray(monthly, float))
    peak = np.maximum.accumulate(c)
    return float((c - peak).min())


def perf(monthly: pd.Series) -> dict:
    x = monthly.dropna().values
    n = x.size
    mu, sd = x.mean(), x.std(ddof=1)
    ann_ret = mu * 12
    ann_vol = sd * np.sqrt(12)
    return {
        "n_months": int(n),
        "mean_monthly": float(mu),
        "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol),
        "sharpe": float(ann_ret / ann_vol) if ann_vol > 0 else np.nan,
        "nw_tstat": nw_tstat(x),
        "hit_rate": float((x > 0).mean()),
        "max_drawdown": max_drawdown(x),
        "skew": float(pd.Series(x).skew()),
    }


# ---------------------------------------------------------------------------
# portfolio construction
# ---------------------------------------------------------------------------
def leg_returns(df: pd.DataFrame, ret_col: str, wt_col: str | None,
                nq: int) -> pd.DataFrame:
    """For one monthly cross-section universe, assign quantiles on dislocation and return
    per-month long(top)-minus-short(bottom) spread plus leg means/weights for turnover.

    wt_col=None -> equal weight firms; else weight firms by wt_col within a leg.
    Returns one row per (ym) with columns: ret_ls, w_long(dict not stored here).
    """
    out = []
    holdings = {}  # ym -> dict(permco -> signed weight) for turnover
    for ym, g in df.dropna(subset=["dislocation", ret_col]).groupby("ym"):
        if g["permco"].nunique() < nq * 2:  # need enough names to form quantiles
            continue
        q = pd.qcut(g["dislocation"].rank(method="first"), nq, labels=False)
        g = g.assign(q=q.values)
        top = g[g["q"] == nq - 1]
        bot = g[g["q"] == 0]
        if len(top) == 0 or len(bot) == 0:
            continue

        def wmean(sub):
            if wt_col is None:
                return sub[ret_col].mean(), pd.Series(1.0 / len(sub), index=sub["permco"].values)
            w = sub[wt_col].clip(lower=0).astype(float)
            if w.sum() <= 0:
                return sub[ret_col].mean(), pd.Series(1.0 / len(sub), index=sub["permco"].values)
            wn = w / w.sum()
            return float((sub[ret_col].values * wn.values).sum()), pd.Series(wn.values, index=sub["permco"].values)

        r_long, w_long = wmean(top)
        r_short, w_short = wmean(bot)
        out.append({"ym": ym, "r_long": r_long, "r_short": r_short,
                    "ret_ls": r_long - r_short, "n_long": len(top), "n_short": len(bot)})
        signed = {p: +w for p, w in w_long.items()}
        for p, w in w_short.items():
            signed[p] = signed.get(p, 0.0) - w
        holdings[ym] = signed
    res = pd.DataFrame(out).sort_values("ym").reset_index(drop=True)
    return res, holdings


def avg_turnover(holdings: dict) -> float:
    """Average one-sided turnover: 0.5 * sum_i |w_{t} - w_{t-1}| across rebalances."""
    yms = sorted(holdings.keys())
    tos = []
    for prev, cur in zip(yms[:-1], yms[1:]):
        hp, hc = holdings[prev], holdings[cur]
        names = set(hp) | set(hc)
        to = 0.5 * sum(abs(hc.get(n, 0.0) - hp.get(n, 0.0)) for n in names)
        tos.append(to)
    return float(np.mean(tos)) if tos else np.nan


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    sig = pd.read_parquet(C.PROCESSED / "signal_panel.parquet")
    panel = pd.read_parquet(C.PROCESSED / "panel_firm_month.parquet")

    # firm AO total (for AO-across-firms robustness portfolio weight)
    sig = sig.merge(panel[["permco", "ym", "bond_ao_total"]], on=["permco", "ym"], how="left")

    # credit-excess forward return bd_xs_{t+1} and duration at t (duration-gap diagnostic)
    fm, _ = build_firm_rate_vars()                      # permco, ym(Period), bd_xs, ao_dur
    fm["ym"] = fm["ym"].astype(str)
    sig = sig.merge(fm.rename(columns={"ao_dur": "ao_dur_t"})[["permco", "ym", "ao_dur_t"]],
                    on=["permco", "ym"], how="left")
    xf = fm[["permco", "ym", "bd_xs"]].copy()
    xf["ym"] = (pd.PeriodIndex(xf["ym"], freq="M") - 1).astype(str)   # carry t+1 value back to t
    xf = xf.rename(columns={"bd_xs": "bd_xs_fwd1"})
    sig = sig.merge(xf, on=["permco", "ym"], how="left")

    sig["ig"] = sig["frac_ig_ao"] >= 0.5
    universes = {"ALL": sig, "HY": sig[~sig["ig"]].copy(), "IG": sig[sig["ig"]].copy()}

    # (sleeve, return-definition, portfolio-weighting) specs
    #   primary return  = credit-excess (duration-matched Treasury hedged) bd_xs_fwd1
    #   robustness ret  = raw bond return bond_ret_ao_fwd1
    #   primary weight  = equal-weight firms (wt=None)
    #   robustness wt   = AO across firms (wt=bond_ao_total)
    ret_specs = {"credit_excess": "bd_xs_fwd1", "raw_bond": "bond_ret_ao_fwd1"}
    wt_specs = {"EW_firms": None, "AO_firms": "bond_ao_total"}

    summary_rows = []
    series_store = {}       # label -> monthly ret_ls series (for plot + cost grid)
    turnover_store = {}     # label -> avg turnover
    durgap_rows = []

    for uname, udf in universes.items():
        for rname, rcol in ret_specs.items():
            for wname, wcol in wt_specs.items():
                res, holdings = leg_returns(udf, rcol, wcol, N_QUANTILES_PRIMARY)
                if res.empty:
                    continue
                label = f"{uname}|{rname}|{wname}|Q5"
                m = perf(res.set_index("ym")["ret_ls"])
                to = avg_turnover(holdings)
                m.update({"sleeve": uname, "return_def": rname, "port_weight": wname,
                          "n_quantiles": N_QUANTILES_PRIMARY, "avg_turnover": to,
                          "avg_n_long": float(res["n_long"].mean()),
                          "avg_n_short": float(res["n_short"].mean())})
                summary_rows.append(m)
                series_store[label] = res.set_index("ym")["ret_ls"]
                turnover_store[label] = to

        # duration-gap diagnostic (primary EW, credit-excess universe): Q5 - Q1 AO-duration
        dd = udf.dropna(subset=["dislocation", "ao_dur_t"])
        gaps = []
        for ym, g in dd.groupby("ym"):
            if g["permco"].nunique() < N_QUANTILES_PRIMARY * 2:
                continue
            q = pd.qcut(g["dislocation"].rank(method="first"), N_QUANTILES_PRIMARY, labels=False)
            g = g.assign(q=q.values)
            top = g[g["q"] == N_QUANTILES_PRIMARY - 1]["ao_dur_t"].mean()
            bot = g[g["q"] == 0]["ao_dur_t"].mean()
            gaps.append(top - bot)
        durgap_rows.append({"sleeve": uname, "mean_dur_gap_Q5_minus_Q1_yrs": float(np.nanmean(gaps)),
                            "std_dur_gap_yrs": float(np.nanstd(gaps))})

    # deciles robustness (ALL & HY, primary return/weight)
    for uname in ["ALL", "HY", "IG"]:
        res, holdings = leg_returns(universes[uname], "bd_xs_fwd1", None, 10)
        if res.empty:
            continue
        m = perf(res.set_index("ym")["ret_ls"])
        m.update({"sleeve": uname, "return_def": "credit_excess", "port_weight": "EW_firms",
                  "n_quantiles": 10, "avg_turnover": avg_turnover(holdings),
                  "avg_n_long": float(res["n_long"].mean()),
                  "avg_n_short": float(res["n_short"].mean())})
        summary_rows.append(m)

    summ = pd.DataFrame(summary_rows)
    col_order = ["sleeve", "return_def", "port_weight", "n_quantiles", "n_months",
                 "mean_monthly", "ann_return", "ann_vol", "sharpe", "nw_tstat", "hit_rate",
                 "max_drawdown", "skew", "avg_turnover", "avg_n_long", "avg_n_short"]
    summ = summ[col_order].sort_values(["n_quantiles", "return_def", "port_weight", "sleeve"])
    summ.round(5).to_csv(C.TABLES / "backtest_summary.csv", index=False)

    durgap = pd.DataFrame(durgap_rows)

    # ------------------------------------------------------------------ cost grid (ILLUSTRATIVE)
    # Primary portfolios: {ALL,HY,IG} | credit_excess | EW_firms | Q5
    cost_rows = []
    for uname in ["ALL", "HY", "IG"]:
        label = f"{uname}|credit_excess|EW_firms|Q5"
        if label not in series_store:
            continue
        gross = series_store[label]
        to = turnover_store[label]
        for bp in COST_GRID_BP:
            # cost per rebalance applied to BOTH legs: total traded notional per month
            # ~ 2 * one-sided turnover (long side + short side); gross book = 2 (long+short).
            # monthly cost = (bp/1e4) * (traded fraction of the 2-unit gross book)
            monthly_cost = (bp / 1e4) * (2.0 * to)
            net = gross - monthly_cost
            mm = perf(net)
            cost_rows.append({"sleeve": uname, "illustrative_cost_bp_roundtrip": bp,
                              "monthly_cost_drag": monthly_cost,
                              "net_ann_return": mm["ann_return"], "net_sharpe": mm["sharpe"],
                              "net_mean_monthly": mm["mean_monthly"]})
    costs = pd.DataFrame(cost_rows)
    costs.round(6).to_csv(C.TABLES / "backtest_cost_sensitivity.csv", index=False)

    # ------------------------------------------------------------------ per-month returns (primary)
    prim_cols = {}
    for uname in ["ALL", "HY", "IG"]:
        label = f"{uname}|credit_excess|EW_firms|Q5"
        if label in series_store:
            prim_cols[f"{uname}_ret_ls"] = series_store[label]
    prim = pd.DataFrame(prim_cols)
    prim.index.name = "ym"
    prim.round(6).to_csv(C.TABLES / "backtest_portfolio_returns.csv")

    # ------------------------------------------------------------------ figure (cumulative)
    fig, ax = plt.subplots(figsize=(9, 4))
    for uname, c in zip(["ALL", "HY", "IG"], ["C0", "C3", "C2"]):
        label = f"{uname}|credit_excess|EW_firms|Q5"
        if label not in series_store:
            continue
        s = series_store[label]
        ts = pd.PeriodIndex(s.index, freq="M").to_timestamp()
        ax.plot(ts, s.cumsum().values, label=f"{uname} (EW, credit-excess)", color=c, lw=1.5)
    ax.axhline(0, color="grey", lw=0.6)
    ax.set_title("Candidate A — cumulative monthly L/S credit-excess return (gross, additive)")
    ax.set_ylabel("cumulative monthly spread"); ax.legend()
    fig.tight_layout(); fig.savefig(C.FIGURES / "backtest_cumret.png", dpi=120); plt.close(fig)

    # ------------------------------------------------------------------ write diagnostics
    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 4 — Candidate A backtest (gross + illustrative costs)\n\nGenerated {utc_now_iso()}\n")
    W("Cross-sectional monthly long/short on the frozen no-look-ahead dislocation signal "
      "(`Dislocation_{i,t}=eq_t-(alpha_t+beta_t*bd_t)`, alpha/beta on s<=t-1). "
      f"Quintiles (primary): LONG Q5, SHORT Q1, dollar-neutral, 1-month hold, monthly rebalance. "
      f"Signal months {sig['ym'].min()}..{sig['ym'].max()}.")
    W("\n**Weighting (two layers):** within firm = AO-weighted bonds (Phase 2); across firms = "
      "**equal-weight firms (PRIMARY)**; AO-across-firms (firm `bond_ao_total`) = robustness.")
    W("**Return:** credit-excess (duration-matched Treasury-hedged) = PRIMARY; raw bond return = "
      "robustness. All returns are additive monthly spreads (bond total/excess returns).\n")

    W("## Performance summary\n")
    show = summ.copy()
    for c in ["mean_monthly", "ann_return", "ann_vol", "max_drawdown", "avg_turnover"]:
        show[c] = (show[c] * 100).round(2)        # to %
    show["sharpe"] = show["sharpe"].round(2); show["nw_tstat"] = show["nw_tstat"].round(2)
    show["hit_rate"] = (show["hit_rate"] * 100).round(1); show["skew"] = show["skew"].round(2)
    show = show.rename(columns={"mean_monthly": "mean_mo_%", "ann_return": "ann_ret_%",
                                "ann_vol": "ann_vol_%", "max_drawdown": "maxDD_%",
                                "avg_turnover": "turnover_%"})
    W(show.to_markdown(index=False))
    W("\n_`turnover_%` = average one-sided turnover per rebalance (0.5·Σ|Δw|). "
      "Returns are monthly L/S spreads; ann. figures = mean×12 and sd×√12; Sharpe = ann_ret/ann_vol; "
      "`nw_tstat` = Newey-West (3 lag) t-stat of the monthly mean; maxDD on cumulative additive spread._\n")

    W("## Duration-gap diagnostic (primary quintiles)\n")
    W("AO-weighted duration difference Q5−Q1 (years). Credit-excess returns already Treasury-hedge "
      "each leg; a small gap confirms the L/S is not a duration bet.\n")
    W(durgap.round(3).to_markdown(index=False))

    W("\n## Transaction-cost sensitivity — ILLUSTRATIVE ONLY\n")
    W("**These bp levels are illustrative assumptions, NOT estimated transaction costs.** "
      "`t_spread` is not used (its meaning is unverified; it is not a confirmed bid-ask measure), and "
      "we have no defensible observed executable bid-ask for these bonds. Monthly cost drag = "
      "(cost_bp/1e4) × 2 × one-sided turnover (both legs). Primary portfolios "
      "(credit-excess, EW firms, quintiles):\n")
    cshow = costs.copy()
    cshow["monthly_cost_drag"] = (cshow["monthly_cost_drag"] * 100).round(3)
    cshow["net_ann_return"] = (cshow["net_ann_return"] * 100).round(2)
    cshow["net_mean_monthly"] = (cshow["net_mean_monthly"] * 100).round(3)
    cshow["net_sharpe"] = cshow["net_sharpe"].round(2)
    cshow = cshow.rename(columns={"monthly_cost_drag": "mo_cost_drag_%",
                                  "net_ann_return": "net_ann_ret_%",
                                  "net_mean_monthly": "net_mean_mo_%"})
    W(cshow.to_markdown(index=False))

    W("\n## Caveats (carry into the pitch)\n")
    W("- This is a **bond** trade exploiting a robust predictive relation `eq_t→bd_{t+1}`; it is "
      "**not** proof of causal information diffusion.")
    W("- Per-name edge is modest; the strategy needs breadth and low costs. Single-name cash-bond "
      "**shorting is impractical/expensive in reality** — Candidate A is the research/backtest vehicle; "
      "real-world expression would use CDS/CDX/ETF (untested here).")
    W("- The relation may invert in liquidity/crisis regimes (correlations spike, bonds gap).")
    W("- Cost levels above are illustrative; realistic costs are higher in HY than IG.")

    (C.DIAGNOSTICS / "phase4_backtest.md").write_text("\n".join(S) + "\n")
    write_json(C.DIAGNOSTICS / "phase4_backtest.json",
               {"generated_utc": utc_now_iso(),
                "signal_months": [sig["ym"].min(), sig["ym"].max()],
                "summary": summ.to_dict(orient="records"),
                "duration_gap": durgap.to_dict(orient="records"),
                "cost_sensitivity_illustrative": costs.to_dict(orient="records"),
                "notes": "t_spread NOT used; all cost bp are illustrative assumptions, not estimates."})
    log.info("Wrote Phase-4 backtest outputs (%d summary rows)", len(summ))
    print("\n".join(S))


if __name__ == "__main__":
    main()
