"""
Phase 4 — Current-dislocation snapshot (as-of latest available month, 2025-11).

Uses the EXACT frozen signal from signal_panel.parquet:
  Dislocation_{i,t} = eq_t - (alpha_t + beta_t * bd_t), (alpha_t,beta_t) from the frozen
  expanding pooled regression on s<=t-1 (no look-ahead). NO re-estimation, NO new predictors,
  NO future data. We simply read the already-computed month-t=2025-11 scores and describe them.

Deliverables (DIAGNOSTIC ONLY — not trade recommendations):
  1. score the latest month (2025-11);
  2. cross-sectional distribution of Dislocation + dispersion vs history;
  3. current Q5 / Q1 membership (same quintile construction as the backtest);
  4. most extreme +/- signals;
  5. data-driven idiosyncratic-confound flags (stale/abnormal print, thin issuance, extreme
     single-month move, distress/default rating) + identifiers so external events (M&A, earnings,
     rating actions, cap-structure changes) can be verified OUTSIDE our data;
  6. ALL / HY / IG separated where useful;
  7. shortlist 1-2 CLEAN candidate examples for the pitch (explicitly not recommendations).

Reads existing files only; writes NEW outputs. Does not modify any prior file.
Run: conda run -n credit-equity python -m src.current_snapshot
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()

ASOF = "2025-11"
NQ = 5
DISTRESS_CATS = {"CCC", "CC", "C", "D"}
STALE_AOW_DAYS = 7      # AO-weighted days-from-last-trade-to-month-end threshold (2d = calendar floor)
STALE_MAX_DAYS = 15     # any-bond staleness threshold
BIG_EQUITY_MOVE = 0.30  # |monthly equity return| that likely signals an idiosyncratic event


def firm_identity(permco_keep: set) -> pd.DataFrame:
    """permco -> (ticker, issuernm) at ASOF, taking the largest-cap share class."""
    e = pd.read_parquet(C.INTERIM / "equity_clean.parquet")
    e = e[(e["yyyymm"] == int(ASOF.replace("-", ""))) & e["permco"].isin(permco_keep)].copy()
    e["mthcap"] = pd.to_numeric(e["mthcap"], errors="coerce")
    e = e.sort_values("mthcap").drop_duplicates("permco", keep="last")
    return e[["permco", "ticker", "issuernm"]]


def bond_screens(permco_keep: set) -> pd.DataFrame:
    """Firm-level confound screens at ASOF from existing bond files."""
    bl = pd.read_parquet(C.INTERIM / "bonds_linked.parquet")
    bl["date"] = pd.to_datetime(bl["date"]); bl["ym"] = bl["date"].dt.to_period("M")
    bl = bl[(bl["ym"].astype(str) == ASOF) & bl["permco"].isin(permco_keep)].copy()
    bl["amount_outstanding"] = pd.to_numeric(bl["amount_outstanding"], errors="coerce").clip(lower=0)

    # freshness: days from price-setting trade to month-end
    lq = pd.read_parquet(C.RAW / "bond_liquidity.parquet")
    lq["date"] = pd.to_datetime(lq["date"]); lq["t_date"] = pd.to_datetime(lq["t_date"])
    lq = lq[lq["date"].dt.to_period("M").astype(str) == ASOF][["cusip", "date", "t_date"]]
    bl = bl.merge(lq, on=["cusip", "date"], how="left")
    bl["days_eom"] = (bl["date"] - bl["t_date"]).dt.days

    bl["is_distress"] = bl["rating_cat"].astype(str).isin(DISTRESS_CATS) | (bl["defaulted"].astype(str) == "Y")
    bl["w"] = bl["amount_outstanding"]
    g = bl.groupby("permco")
    out = pd.DataFrame({
        "aow_days_eom": g.apply(lambda d: np.average(d["days_eom"].fillna(d["days_eom"].max()),
                                weights=d["w"].where(d["w"] > 0, 1.0)), include_groups=False),
        "max_days_eom": g["days_eom"].max(),
        "any_distress": g["is_distress"].any(),
        "any_default": g.apply(lambda d: (d["defaulted"].astype(str) == "Y").any(), include_groups=False),
        "worst_rating": g["rating_cat"].apply(lambda s: _worst_rating(s)),
        "all_nr": g["rating_cat"].apply(lambda s: (s.astype(str) == "NR").all()),
        "company_symbol": g["company_symbol"].apply(lambda s: ";".join(sorted(set(s.dropna().astype(str))))[:60]),
        "n_cusips": g["cusip"].nunique(),
    }).reset_index()
    return out


_RANK = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
def _worst_rating(s: pd.Series) -> str:
    vals = [v for v in s.astype(str).unique() if v in _RANK]
    return max(vals, key=lambda v: _RANK.index(v)) if vals else "NR"


def dispersion_history(sig: pd.DataFrame, mask_name: str, sub: pd.DataFrame) -> dict:
    """Per-month cross-sectional std & IQR of dislocation; where ASOF ranks."""
    by = sub.groupby("ym")["dislocation"].agg(
        std="std", iqr=lambda x: x.quantile(.75) - x.quantile(.25), n="count")
    by = by[by["n"] >= NQ * 2]
    cur = by.loc[ASOF]
    return {
        "sleeve": mask_name,
        "asof_n": int(cur["n"]),
        "asof_std": float(cur["std"]), "asof_iqr": float(cur["iqr"]),
        "hist_median_std": float(by["std"].median()), "hist_median_iqr": float(by["iqr"].median()),
        "std_pctile": float((by["std"] < cur["std"]).mean() * 100),
        "iqr_pctile": float((by["iqr"] < cur["iqr"]).mean() * 100),
        "n_months": int(len(by)),
    }


def quintile(series: pd.Series, nq: int = NQ) -> pd.Series:
    return pd.qcut(series.rank(method="first"), nq, labels=False) + 1


def main() -> None:
    sig = pd.read_parquet(C.PROCESSED / "signal_panel.parquet")
    nov = sig[sig["ym"] == ASOF].copy()
    assert len(nov) > 0, f"no rows for {ASOF}"
    nov["sleeve"] = np.where(nov["frac_ig_ao"] >= 0.5, "IG", "HY")

    ident = firm_identity(set(nov["permco"]))
    screens = bond_screens(set(nov["permco"]))
    nov = nov.merge(ident, on="permco", how="left").merge(screens, on="permco", how="left")

    # z-score within ASOF cross-section; quintiles (ALL, and within sleeve)
    mu, sd = nov["dislocation"].mean(), nov["dislocation"].std()
    nov["z_all"] = (nov["dislocation"] - mu) / sd
    nov["q_all"] = quintile(nov["dislocation"])
    nov["q_sleeve"] = nov.groupby("sleeve")["dislocation"].transform(quintile)

    # confound flags
    smallcap_cut = nov["firm_mktcap"].quantile(0.10)
    bret_hi = nov["bond_ret_ao"].abs().quantile(0.99)
    nov["flag_thin"] = nov["n_bonds"] <= 1
    nov["flag_stale"] = (nov["aow_days_eom"] > STALE_AOW_DAYS) | (nov["max_days_eom"] > STALE_MAX_DAYS)
    nov["flag_extreme_bond"] = nov["bond_ret_ao"].abs() > bret_hi
    nov["flag_extreme_equity"] = nov["equity_ret"].abs() > BIG_EQUITY_MOVE
    nov["flag_distress"] = nov["any_distress"].fillna(False)
    nov["flag_smallcap"] = nov["firm_mktcap"] < smallcap_cut   # soft caveat
    nov["flag_nr"] = nov["all_nr"].fillna(False)               # soft caveat
    HARD = ["flag_thin", "flag_stale", "flag_extreme_bond", "flag_extreme_equity", "flag_distress"]
    nov["hard_flags"] = nov[HARD].sum(axis=1)
    nov["clean"] = nov["hard_flags"] == 0

    # ---- outputs: full scored table ----
    show_cols = ["permco", "ticker", "issuernm", "company_symbol", "sleeve", "dislocation",
                 "z_all", "q_all", "q_sleeve", "bond_ret_ao", "equity_ret", "eq_implied",
                 "n_bonds", "firm_mktcap", "worst_rating", "aow_days_eom", "max_days_eom",
                 "flag_thin", "flag_stale", "flag_extreme_bond", "flag_extreme_equity",
                 "flag_distress", "flag_smallcap", "flag_nr", "hard_flags", "clean"]
    nov_out = nov[show_cols].sort_values("dislocation", ascending=False).reset_index(drop=True)
    nov_out.round(5).to_csv(C.TABLES / "current_snapshot_scores.csv", index=False)

    # ---- dispersion vs history ----
    disp = [dispersion_history(sig, "ALL", sig),
            dispersion_history(sig, "HY", sig[sig["frac_ig_ao"] < 0.5]),
            dispersion_history(sig, "IG", sig[sig["frac_ig_ao"] >= 0.5])]
    disp_df = pd.DataFrame(disp)

    # ---- extremes (ALL) ----
    ext_cols = ["ticker", "issuernm", "sleeve", "dislocation", "z_all", "q_all",
                "bond_ret_ao", "equity_ret", "n_bonds", "worst_rating", "aow_days_eom",
                "hard_flags", "clean"]
    top_pos = nov_out.head(12)[ext_cols]
    top_neg = nov_out.tail(12)[ext_cols].iloc[::-1]
    top_pos.round(4).to_csv(C.TABLES / "current_extremes_positive.csv", index=False)
    top_neg.round(4).to_csv(C.TABLES / "current_extremes_negative.csv", index=False)

    # ---- clean candidate shortlist (not recommendations) ----
    # most extreme CLEAN names on each side; prefer HY for economic strength.
    cand_pos = nov[nov["clean"]].sort_values("dislocation", ascending=False)
    cand_neg = nov[nov["clean"]].sort_values("dislocation", ascending=True)
    def pick(df, side):
        hy = df[df["sleeve"] == "HY"].head(1)
        other = df[~df["permco"].isin(hy["permco"])].head(2)
        return pd.concat([hy, other]).head(3).assign(side=side)
    cand = pd.concat([pick(cand_pos, "positive(equity>bond-implied)"),
                      pick(cand_neg, "negative(equity<bond-implied)")])
    cand_cols = ["side", "ticker", "issuernm", "company_symbol", "sleeve", "dislocation", "z_all",
                 "q_all", "q_sleeve", "bond_ret_ao", "equity_ret", "n_bonds", "firm_mktcap",
                 "worst_rating", "aow_days_eom", "flag_smallcap", "flag_nr"]
    cand = cand[cand_cols].reset_index(drop=True)
    cand.round(5).to_csv(C.TABLES / "current_candidates.csv", index=False)

    # ---- figure: ASOF distribution vs pooled history ----
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist(sig["dislocation"][sig["dislocation"].abs() < 0.4], bins=120, density=True,
            alpha=.45, color="grey", label="pooled history 2017-01..2025-11")
    ax.hist(nov["dislocation"][nov["dislocation"].abs() < 0.4], bins=40, density=True,
            alpha=.6, color="C0", label=f"{ASOF} cross-section")
    ax.axvline(0, color="k", lw=.6)
    ax.set_title(f"Dislocation: {ASOF} vs history"); ax.set_xlabel("dislocation"); ax.legend()
    fig.tight_layout(); fig.savefig(C.FIGURES / "current_dislocation_hist.png", dpi=120); plt.close(fig)

    # ------------------------------------------------------------------ write markdown
    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 4 — Current-dislocation snapshot (as-of {ASOF})\n\nGenerated {utc_now_iso()}\n")
    W("Frozen signal, no re-estimation / no future data: "
      "`Dislocation_{i,t}=eq_t-(alpha_t+beta_t*bd_t)` with alpha/beta from the expanding model on "
      "s<=t-1. **Diagnostic only — nothing below is a trade recommendation.** Forward bond return for "
      f"{ASOF} is unavailable (bond data end {ASOF}); this scores the signal, it does not evaluate P&L.\n")

    W("## 1-2. Cross-sectional distribution & dispersion vs history\n")
    d = nov["dislocation"]
    W(f"- {ASOF}: **{len(nov)} firms** (HY {int((nov['sleeve']=='HY').sum())}, "
      f"IG {int((nov['sleeve']=='IG').sum())}). mean {d.mean():.4f}, median {d.median():.4f}, "
      f"std {d.std():.4f}, IQR {d.quantile(.75)-d.quantile(.25):.4f}, "
      f"min {d.min():.4f}, max {d.max():.4f}.")
    W(f"- Mean is modestly **positive** ({d.mean():+.4f}): Nov-2025 equities broadly outran their "
      "bond-implied move (a common/market tilt). A cross-sectional Q5−Q1 nets out most of this level.\n")
    W("Dispersion percentile = where this month's cross-sectional spread sits within the 107-month "
      "history (50 = typical, >80 = unusually dispersed):\n")
    W(disp_df.round(4).to_markdown(index=False))
    W("")

    W("## 3. Current quintiles (same construction as the backtest)\n")
    qn = nov.groupby("q_all").size()
    W(f"- ALL quintiles by dislocation: " + ", ".join(f"Q{int(k)}={v}" for k, v in qn.items()) +
      f". **Q5 (long-credit side) = {int((nov['q_all']==NQ).sum())} names**, "
      f"**Q1 (short-credit side) = {int((nov['q_all']==1).sum())} names**.")
    W("- Within-sleeve quintiles (`q_sleeve`) are in `current_snapshot_scores.csv` for the HY-only and "
      "IG-only books. Full Q5/Q1 membership is in that file (columns `q_all`,`q_sleeve`).\n")

    W("## 4. Most extreme signals\n")
    W(f"**Top positive (equity outran bonds → signal says bond may catch up), {ASOF}:**\n")
    W(top_pos.round(4).to_markdown(index=False))
    W(f"\n**Top negative (equity lagged bonds → signal says bond may underperform), {ASOF}:**\n")
    W(top_neg.round(4).to_markdown(index=False))

    W("\n## 5. Idiosyncratic-confound flags (make a name non-comparable to the historical relation)\n")
    W("Data-driven flags computed from our files:")
    W(f"- `flag_stale`: AO-weighted days from last trade to month-end > {STALE_AOW_DAYS}, or any bond "
      f"> {STALE_MAX_DAYS} (within-month stale/asynchronous print). NB a 2-day floor is a calendar "
      "artifact (2025-11-30 is a Sunday).")
    W(f"- `flag_thin`: single-bond firm. `flag_extreme_bond`: |bond return| above the {ASOF} 99th pct "
      f"(possible abnormal print). `flag_extreme_equity`: |equity return| > {BIG_EQUITY_MOVE:.0%} "
      "(likely an idiosyncratic equity event). `flag_distress`: any bond rated CCC/CC/C/D or defaulted.")
    W("- Soft caveats: `flag_smallcap` (bottom-decile firm cap), `flag_nr` (all bonds unrated).")
    flagged = nov[HARD].any(axis=1).sum()
    W(f"- {int(flagged)}/{len(nov)} firms carry ≥1 hard flag; {int(nov['clean'].sum())} are 'clean'. "
      "Counts per flag: " + ", ".join(f"{c}={int(nov[c].sum())}" for c in HARD) +
      f", flag_smallcap={int(nov['flag_smallcap'].sum())}, flag_nr={int(nov['flag_nr'].sum())}.")
    W("- **NOT detectable from our data (require external verification before trusting any name):** "
      "M&A/tender offers, earnings surprises, rating-agency actions, capital-structure changes, "
      "guidance/litigation. Identifiers for lookup (`ticker`,`issuernm`,`company_symbol`) are in the "
      "candidate/extremes tables. Treat all names as leads to verify, not conclusions.\n")

    W("## 6-7. Clean candidate examples for the pitch (verify events externally; NOT recommendations)\n")
    W("Most extreme **clean** names (no hard flags) on each side; HY shown first where available "
      "because the historical effect is ~6× larger there:\n")
    W(cand.round(4).to_markdown(index=False))
    W("\nFor the 10-minute pitch, pick **one positive and one negative clean name** (ideally including "
      "an HY name) and, before the talk, confirm there is no M&A/earnings/rating event explaining the "
      "gap — if clean, it illustrates 'equity has moved, same-firm bonds have not yet' as of "
      f"{ASOF}. This snapshot is the current instance of exactly the book the backtest traded.")

    (C.DIAGNOSTICS / "phase4_current_snapshot.md").write_text("\n".join(S) + "\n")
    write_json(C.DIAGNOSTICS / "phase4_current_snapshot.json",
               {"generated_utc": utc_now_iso(), "asof": ASOF,
                "n_firms": int(len(nov)), "dispersion": disp,
                "cross_section": {"mean": float(d.mean()), "std": float(d.std()),
                                  "iqr": float(d.quantile(.75) - d.quantile(.25)),
                                  "min": float(d.min()), "max": float(d.max())},
                "n_clean": int(nov["clean"].sum()),
                "flag_counts": {c: int(nov[c].sum()) for c in HARD + ["flag_smallcap", "flag_nr"]},
                "candidates": cand.to_dict(orient="records"),
                "note": "Diagnostic only; no trade recommendation; M&A/earnings/rating events need external check."})
    log.info("Wrote current-snapshot outputs (%d firms, %d clean)", len(nov), int(nov["clean"].sum()))
    print("\n".join(S))


if __name__ == "__main__":
    main()
