"""
Phase 3 robustness — rate/duration & IG-HY tests of the equity->bond result.

Builds, from the primary linked-bond universe:
  - firm AO-weighted duration (years), validity 0 < duration <= tmt
  - bond-level duration-matched Treasury return (interp over 1/2/5/7/10/20/30y points, by
    duration-in-years, same month), CreditExcess = ret_eom - Tsy_matched; AO-aggregated to firm
  - Delta y10 (10y Treasury yield change) for the duration x rate-move control

Specs (signal-month FE, two-way clustered SE):
  Baseline : bd_{t+1}    ~ bd_t   + eq_t
  Spec A   : bd_{t+1}    ~ bd_t   + eq_t + AOdur_t + AOdur_t * Dy10_{t+1}
  Spec B   : bd_xs_{t+1} ~ bd_xs_t+ eq_t
  Spec C   : Baseline/A/B split IG (frac_ig_ao>=0.5) vs HY (<0.5)

TIMING: eq_t, bd_t, AOdur_t, bd_xs_t are all dated t (known at signal time). Dy10_{t+1} is the
REALIZED t+1 yield change -> an ex-post control to purge the dependent's rate component, NOT a
tradable time-t predictor. Duration matching uses contemporaneous (month-tau) duration on both
corporate and Treasury sides (durations are persistent; lagged-duration = later robustness).

Run: conda run -n credit-equity python -m src.rate_robustness
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()


def build_firm_rate_vars():
    bl = pd.read_parquet(C.INTERIM / "bonds_linked.parquet")
    bl["date"] = pd.to_datetime(bl["date"]); bl["ym"] = bl["date"].dt.to_period("M")
    for c in ["duration", "tmt", "amount_outstanding", "ret_eom"]:
        bl[c] = pd.to_numeric(bl[c], errors="coerce")
    valid = (bl["duration"] > 0) & (bl["duration"] <= bl["tmt"]) & bl["amount_outstanding"].gt(0)
    bl = bl[valid].copy()

    tr = pd.read_parquet(C.RAW / "treasury_ft.parquet")
    tr["ym"] = pd.to_datetime(tr["mcaldt"]).dt.to_period("M")
    tr["dur_y"] = tr["tmduratn"] / 365.25
    tr["ret"] = tr["tmretadj"] / 100.0
    # per-month duration grid -> interpolate bond duration to a matched Treasury return
    bl["tsy_matched"] = np.nan
    for ym, g in tr.groupby("ym"):
        gg = g.sort_values("dur_y")
        xp, fp = gg["dur_y"].values, gg["ret"].values
        mask = bl["ym"] == ym
        if mask.any():
            bl.loc[mask, "tsy_matched"] = np.interp(bl.loc[mask, "duration"].values, xp, fp)
    bl["credit_excess"] = bl["ret_eom"] - bl["tsy_matched"]

    w = bl["amount_outstanding"]
    bl["xw"] = bl["credit_excess"] * w; bl["dw"] = bl["duration"] * w
    fm = bl.groupby(["permco", "ym"]).agg(
        ao=("amount_outstanding", "sum"), xw=("xw", "sum"), dw=("dw", "sum")).reset_index()
    fm["bd_xs"] = fm["xw"] / fm["ao"]
    fm["ao_dur"] = fm["dw"] / fm["ao"]

    # Delta y10 by month (yield change over that month), decimal
    y10 = (tr[tr["term_label"] == "10Y"].sort_values("ym")[["ym", "tmytm"]]
           .assign(y=lambda d: d["tmytm"] / 100.0))
    y10["dy10"] = y10["y"].diff()
    return fm[["permco", "ym", "bd_xs", "ao_dur"]], y10[["ym", "dy10"]]


def fit(df, dep, regs, label):
    d = df.dropna(subset=[dep] + regs).copy()
    d["tt"] = d["yyyymm"].astype(int)
    d = d.set_index(["permco", "tt"])
    res = PanelOLS(d[dep], d[regs], time_effects=True).fit(
        cov_type="clustered", cluster_entity=True, cluster_time=True)
    sd_eq = float(d["eq_t"].std())
    return {"spec": label, "d(eq_t)": round(float(res.params["eq_t"]), 4),
            "se": round(float(res.std_errors["eq_t"]), 4),
            "t": round(float(res.tstats["eq_t"]), 2),
            "p": round(float(res.pvalues["eq_t"]), 4),
            "+1SD_bp": round(1e4 * float(res.params["eq_t"]) * sd_eq, 1),
            "N": int(res.nobs)}


def main():
    fm, y10 = build_firm_rate_vars()
    sig = pd.read_parquet(C.PROCESSED / "signal_panel.parquet")
    sig["ymp"] = pd.PeriodIndex(sig["ym"], freq="M")
    sig = sig.rename(columns={"equity_ret": "eq_t", "bond_ret_ao": "bd_t",
                              "bond_ret_ao_fwd1": "bd_tp1"})

    # merge firm rate vars at t
    sig = sig.merge(fm.rename(columns={"ym": "ymp"}), on=["permco", "ymp"], how="left")
    # forward excess return bd_xs_{t+1}
    xf = fm.rename(columns={"bd_xs": "bd_xs_tp1"})[["permco", "ym", "bd_xs_tp1"]].copy()
    xf["ymp"] = xf["ym"] - 1
    sig = sig.merge(xf.drop(columns="ym"), on=["permco", "ymp"], how="left")
    # Dy10 for t+1
    dyn = y10.copy(); dyn["ymp"] = dyn["ym"] - 1
    sig = sig.merge(dyn.rename(columns={"dy10": "dy10_next"})[["ymp", "dy10_next"]],
                    on="ymp", how="left")
    sig["dur_x_dy"] = sig["ao_dur"] * sig["dy10_next"]
    sig["ig"] = sig["frac_ig_ao"] >= 0.5
    sig = sig.rename(columns={"bd_xs": "bd_xs_t"})  # firm credit-excess return at t

    n_base = sig["bd_tp1"].notna().sum()
    n_dur = sig["ao_dur"].notna().sum()
    n_xs = sig["bd_xs_tp1"].notna().sum()

    def run_block(df, tag):
        return [
            fit(df, "bd_tp1", ["bd_t", "eq_t"], f"Baseline{tag}: bd_(t+1)~bd_t+eq_t"),
            fit(df, "bd_tp1", ["bd_t", "eq_t", "ao_dur", "dur_x_dy"],
                f"Spec A{tag}: +AOdur+AOdur*Dy10_(t+1)"),
            fit(df, "bd_xs_tp1", ["bd_xs_t", "eq_t"], f"Spec B{tag}: credit-excess bd"),
        ]

    rows = run_block(sig, " (ALL)")
    rows += run_block(sig[sig["ig"]], " (IG)")
    rows += run_block(sig[~sig["ig"]], " (HY)")
    tab = pd.DataFrame(rows).set_index("spec")

    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 3 — Rate/Duration & IG-HY robustness\n\nGenerated {utc_now_iso()}\n")
    W(f"Sample: {sig['ym'].min()}..{sig['ym'].max()}; signal firm-months with bd_(t+1): "
      f"{int(n_base):,}; with AO-duration: {int(n_dur):,} "
      f"({100*n_dur/len(sig):.1f}%); with credit-excess bd_(t+1): {int(n_xs):,}.")
    W(f"IG firm-months (frac_ig_ao>=0.5): {int(sig['ig'].sum()):,}; HY: {int((~sig['ig']).sum()):,}\n")
    W("Coefficient on **eq_t** (the equity->bond effect `d`), signal-month FE + two-way "
      "clustered SE:\n")
    W(tab.to_markdown())
    W("\n_`+1SD_bp` = d x SD(eq_t) in basis points. Dy10_(t+1) is a realized t+1 control "
      "(ex-post), not a tradable time-t predictor. Duration-matched Treasury return interpolated "
      "linearly across the 1/2/5/7/10/20/30y points by duration-in-years (np.interp clamps bonds "
      "beyond the grid to the endpoints)._")
    W("\n**Interpretation (bounded):** if `d` survives Spec A/B, differential Treasury-rate "
      "exposure alone is unlikely to explain the equity->bond result, making a corporate-bond-"
      "specific / credit-related channel more plausible. The adjusted return still contains "
      "credit-spread, liquidity, and convexity effects, so this is NOT proof of a pure credit "
      "channel. IG/HY results are descriptive/mechanism-supporting, not proof.")

    tab.to_csv(C.TABLES / "rate_robustness.csv")
    (C.DIAGNOSTICS / "phase3_rate_robustness.md").write_text("\n".join(S) + "\n")
    write_json(C.DIAGNOSTICS / "phase3_rate_robustness.json",
               {"generated_utc": utc_now_iso(), "n_base": int(n_base), "n_dur": int(n_dur),
                "n_xs": int(n_xs), "rows": rows})
    log.info("Wrote rate robustness results")
    print("\n".join(S))


if __name__ == "__main__":
    main()
