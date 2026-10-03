"""
Phase 3c — primary t+1 predictive test (+ reverse-direction diagnostic).

PRIMARY (approved):
  eq_{i,t+1} = lambda_t + gamma * Dislocation_{i,t} + eps      (signal-month FE)
  two-way clustered SE (firm permco & signal month). Convergence hypothesis gamma < 0,
  treated as an empirical result. RAW returns, no winsorization.

REVERSE (diagnostic, not assumed):
  bd_{i,t+1} = lambda_t + delta * Dislocation_{i,t} + eps      (signal-month FE)

Also reports a pooled (no-FE) version for context. No portfolios/backtests.
Run: conda run -n credit-equity python -m src.predictive_regressions
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS, PooledOLS

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()


def fit(df, dep, with_fe):
    d = df.dropna(subset=["dislocation", dep]).copy()
    d["t"] = d["yyyymm"].astype(int)
    d = d.set_index(["permco", "t"])
    y = d[dep]
    if with_fe:
        res = PanelOLS(y, d[["dislocation"]], time_effects=True).fit(
            cov_type="clustered", cluster_entity=True, cluster_time=True)
    else:
        X = d[["dislocation"]].assign(const=1.0)[["const", "dislocation"]]
        res = PooledOLS(y, X).fit(
            cov_type="clustered", cluster_entity=True, cluster_time=True)
    p = res.params["dislocation"]; se = res.std_errors["dislocation"]
    return {"coef": float(p), "se": float(se), "t": float(res.tstats["dislocation"]),
            "pval": float(res.pvalues["dislocation"]),
            "n_obs": int(res.nobs), "rsq_within": float(getattr(res, "rsquared_within", np.nan)),
            "rsq": float(res.rsquared), "sd_dislocation": float(d["dislocation"].std())}


def main():
    sig = pd.read_parquet(C.PROCESSED / "signal_panel.parquet")
    n_firms = sig["permco"].nunique(); n_months = sig["ym"].nunique()

    specs = {
        "PRIMARY: eq_{t+1} ~ dislocation + month FE": ("equity_ret_fwd1", True),
        "context: eq_{t+1} ~ dislocation (pooled, no FE)": ("equity_ret_fwd1", False),
        "REVERSE diagnostic: bond_{t+1} ~ dislocation + month FE": ("bond_ret_ao_fwd1", True),
        "context: bond_{t+1} ~ dislocation (pooled, no FE)": ("bond_ret_ao_fwd1", False),
    }
    results = {k: fit(sig, dep, fe) for k, (dep, fe) in specs.items()}

    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 3c — Predictive tests\n\nGenerated {utc_now_iso()}\n")
    W(f"Signal firm-months (with valid t+1 equity): "
      f"{int(sig['equity_ret_fwd1'].notna().sum()):,} | firms {n_firms:,} | "
      f"signal months {sig['ym'].min()}..{sig['ym'].max()} ({n_months})\n")

    rows = []
    for k, r in results.items():
        econ = r["coef"] * r["sd_dislocation"]  # effect of +1 SD dislocation on next-month ret
        rows.append({"specification": k, "coef(gamma/delta)": round(r["coef"], 4),
                     "se": round(r["se"], 4), "t_stat": round(r["t"], 2),
                     "p_value": round(r["pval"], 4), "N": r["n_obs"],
                     "+1SD_effect_bp": round(1e4 * econ, 1)})
    tab = pd.DataFrame(rows).set_index("specification")
    tab.to_csv(C.TABLES / "predictive_results.csv")
    W(tab.to_markdown())
    W("\n_`+1SD_effect_bp` = coefficient × SD(dislocation), i.e. basis-point change in the "
      "next-month return from a one-standard-deviation increase in dislocation._")
    W("\nInterpretation guide (empirical, not assumed): primary gamma<0 ⇒ equity reverts "
      "toward the bond-implied level (convergence / bonds-lead). Reverse delta≈0 with "
      "gamma<0 ⇒ bonds lead equities; delta large with gamma≈0 ⇒ equities lead bonds.")

    write_json(C.DIAGNOSTICS / "phase3c_predictive.json",
               {"generated_utc": utc_now_iso(), "results": results})
    (C.DIAGNOSTICS / "phase3c_predictive.md").write_text("\n".join(S) + "\n")
    log.info("Wrote predictive results")
    print("\n".join(S))


if __name__ == "__main__":
    main()
