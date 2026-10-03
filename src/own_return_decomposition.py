"""
Phase 3 robustness (decomposition) — separate genuine cross-market prediction from
own-asset autocorrelation. Same sample as the primary test (signal_panel, 2017-01..2025-11),
signal-month FE, two-way clustered SE (firm & month).

Regressions:
  (1) eq_{t+1} = lambda_t + a*eq_t + b*bd_t + e      -> b = incremental bond info for equity
  (2) bd_{t+1} = lambda_t + c*bd_t + d*eq_t + e      -> d = incremental equity info for bond
  own-return baselines: eq_{t+1}~eq_t ; bd_{t+1}~bd_t
Run: conda run -n credit-equity python -m src.own_return_decomposition
"""
from __future__ import annotations

import pandas as pd
from linearmodels.panel import PanelOLS

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()


def fit(df, dep, regs):
    d = df.dropna(subset=[dep] + regs).copy()
    d["t"] = d["yyyymm"].astype(int)
    d = d.set_index(["permco", "t"])
    res = PanelOLS(d[dep], d[regs], time_effects=True).fit(
        cov_type="clustered", cluster_entity=True, cluster_time=True)
    out = {"dep": dep, "n_obs": int(res.nobs), "rsq_within": float(res.rsquared_within)}
    for r in regs:
        out[r] = {"coef": float(res.params[r]), "se": float(res.std_errors[r]),
                  "t": float(res.tstats[r]), "p": float(res.pvalues[r])}
    return out


def main():
    sig = pd.read_parquet(C.PROCESSED / "signal_panel.parquet")
    sig = sig.rename(columns={"equity_ret": "eq_t", "bond_ret_ao": "bd_t",
                              "equity_ret_fwd1": "eq_tp1", "bond_ret_ao_fwd1": "bd_tp1"})

    R = {
        "(1) eq_{t+1} ~ eq_t + bd_t": fit(sig, "eq_tp1", ["eq_t", "bd_t"]),
        "(2) bd_{t+1} ~ bd_t + eq_t": fit(sig, "bd_tp1", ["bd_t", "eq_t"]),
        "baseline eq_{t+1} ~ eq_t":   fit(sig, "eq_tp1", ["eq_t"]),
        "baseline bd_{t+1} ~ bd_t":   fit(sig, "bd_tp1", ["bd_t"]),
    }

    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 3 — Own-return decomposition\n\nGenerated {utc_now_iso()}\n")
    W(f"Sample: signal_panel {sig['ym'].min()}..{sig['ym'].max()} "
      f"({sig['ym'].nunique()} months, {sig['permco'].nunique()} firms). "
      f"Signal-month FE; two-way clustered SE (firm & month).\n")

    rows = []
    for name, r in R.items():
        for term, v in r.items():
            if isinstance(v, dict):
                rows.append({"regression": name, "term": term, "coef": round(v["coef"], 4),
                             "se": round(v["se"], 4), "t": round(v["t"], 2),
                             "p": round(v["p"], 4), "N": r["n_obs"]})
    tab = pd.DataFrame(rows).set_index(["regression", "term"])
    tab.to_csv(C.TABLES / "own_return_decomposition.csv")
    W(tab.to_markdown())
    write_json(C.DIAGNOSTICS / "phase3_decomposition.json",
               {"generated_utc": utc_now_iso(), "results": R})
    (C.DIAGNOSTICS / "phase3_decomposition.md").write_text("\n".join(S) + "\n")
    log.info("Wrote decomposition results")
    print("\n".join(S))


if __name__ == "__main__":
    main()
