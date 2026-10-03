"""
Phase 3 robustness — price-freshness test of the equity->bond result.

Tests whether eq_t -> bd_{t+1} is mechanically driven by asynchronous (within-month stale)
month-end bond pricing. Freshness is applied AT THE BOND LEVEL (days from the price-setting
TRACE trade to month-end), BEFORE AO aggregation, and the SAME fresh-at-t bonds are tracked into
t+1 (so the base price P^{eom}_t of bd_{t+1} is fresh).

Spec (unchanged from baseline):  bd_{i,t+1} = lambda_t + c*bd_{i,t} + d*eq_{i,t} + eps
  signal-month FE, two-way clustered SE. Thresholds: freshness<=inf (baseline), <=5d, <=1d.
  Groups: ALL / IG (frac_ig_ao>=0.5) / HY.

Run: conda run -n credit-equity python -m src.freshness_robustness
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()


def build_bond_level():
    bl = pd.read_parquet(C.INTERIM / "bonds_linked.parquet")
    bl["date"] = pd.to_datetime(bl["date"]); bl["ym"] = bl["date"].dt.to_period("M")
    bl["ret_eom"] = pd.to_numeric(bl["ret_eom"], errors="coerce")
    bl["ao"] = pd.to_numeric(bl["amount_outstanding"], errors="coerce")
    bl["ig"] = (bl["rating_class"] == "0.IG").astype(float)

    liq = pd.read_parquet(C.RAW / "bond_liquidity.parquet")
    liq["date"] = pd.to_datetime(liq["date"]); liq["t_date"] = pd.to_datetime(liq["t_date"])
    bl = bl.merge(liq[["cusip", "date", "t_date"]], on=["cusip", "date"], how="left")
    bl["freshness"] = (bl["date"] - bl["t_date"]).dt.days

    # same-bond next-month return: ret_eom at ym+1 for the same cusip (Current in t+1)
    nxt = bl[["cusip", "ym", "ret_eom"]].copy()
    nxt["ym"] = nxt["ym"] - 1
    nxt = nxt.rename(columns={"ret_eom": "ret_next"})
    bl = bl.merge(nxt, on=["cusip", "ym"], how="left")
    return bl


def firm_aggregate(bl_sub):
    d = bl_sub.dropna(subset=["ret_eom", "ao"]).copy()
    d = d[d["ao"] > 0]
    d["r_w"] = d["ret_eom"] * d["ao"]
    d["rn_w"] = d["ret_next"] * d["ao"]              # NaN where ret_next missing
    d["ao_rn"] = np.where(d["ret_next"].notna(), d["ao"], 0.0)
    d["ig_w"] = d["ig"] * d["ao"]
    g = d.groupby(["permco", "ym"]).agg(
        r_w=("r_w", "sum"), ao=("ao", "sum"), rn_w=("rn_w", "sum"),
        ao_rn=("ao_rn", "sum"), ig_w=("ig_w", "sum"), n_bonds=("ao", "size")).reset_index()
    g["bd_t"] = g["r_w"] / g["ao"]
    g["bd_tp1"] = np.where(g["ao_rn"] > 0, g["rn_w"] / g["ao_rn"], np.nan)
    g["frac_ig"] = g["ig_w"] / g["ao"]
    return g[["permco", "ym", "bd_t", "bd_tp1", "frac_ig", "n_bonds"]]


def fit(df, label):
    d = df.dropna(subset=["bd_tp1", "bd_t", "eq_t"]).copy()
    d["tt"] = d["ym"].astype(str).str.replace("-", "").astype(int)
    n_firms, n_months = d["permco"].nunique(), d["ym"].nunique()
    d = d.set_index(["permco", "tt"])
    res = PanelOLS(d["bd_tp1"], d[["bd_t", "eq_t"]], time_effects=True).fit(
        cov_type="clustered", cluster_entity=True, cluster_time=True)
    return {"cell": label, "d(eq_t)": round(float(res.params["eq_t"]), 4),
            "se": round(float(res.std_errors["eq_t"]), 4),
            "t": round(float(res.tstats["eq_t"]), 2), "p": round(float(res.pvalues["eq_t"]), 4),
            "+1SD_bp": round(1e4 * float(res.params["eq_t"]) * float(d["eq_t"].std()), 1),
            "N": int(res.nobs), "firms": int(n_firms), "months": int(n_months)}


def main():
    bl = build_bond_level()
    sig = pd.read_parquet(C.PROCESSED / "signal_panel.parquet")
    sig["ym"] = pd.PeriodIndex(sig["ym"], freq="M")
    eqt = sig[["permco", "ym", "equity_ret"]].rename(columns={"equity_ret": "eq_t"})

    thresholds = {"inf (baseline)": np.inf, "<=5d": 5, "<=1d": 1}
    rows = []
    base_N = {}
    for tname, k in thresholds.items():
        sub = bl if np.isinf(k) else bl[bl["freshness"] <= k]
        fa = firm_aggregate(sub).merge(eqt, on=["permco", "ym"], how="inner")  # same signal frame
        for gname, gdf in [("ALL", fa), ("IG", fa[fa["frac_ig"] >= 0.5]),
                           ("HY", fa[fa["frac_ig"] < 0.5])]:
            r = fit(gdf, f"{gname} | fresh {tname}")
            if tname == "inf (baseline)":
                base_N[gname] = r["N"]
            r["retention_vs_base"] = round(r["N"] / base_N[gname], 3)
            rows.append(r)

    tab = pd.DataFrame(rows).set_index("cell")
    tab = tab[["d(eq_t)", "se", "t", "p", "+1SD_bp", "N", "firms", "months", "retention_vs_base"]]

    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 3 — Price-freshness robustness (equity->bond)\n\nGenerated {utc_now_iso()}\n")
    W("Freshness = days from price-setting TRACE trade (t_date) to month-end, applied at the "
      "BOND level before AO aggregation; same fresh-at-t bonds tracked into t+1. Spec "
      "`bd_(t+1) ~ bd_t + eq_t`, signal-month FE, two-way clustered SE. `d` = eq_t coefficient.\n")
    W(tab.to_markdown())
    W("\n_Baseline here is reconstructed with same-bond forward returns, so it may differ slightly "
      "from the earlier reverse baseline (d=0.030); the apples-to-apples comparison is across "
      "freshness thresholds within this table._")
    W("\n**Interpretation (bounded):** if `d` stays economically and statistically meaningful at "
      "the 1-day restriction, simple month-end stale/asynchronous pricing is LESS LIKELY to "
      "explain the result. This is NOT proof of information diffusion (other liquidity/mechanism "
      "confounds remain untested).")

    tab.to_csv(C.TABLES / "freshness_robustness.csv")
    (C.DIAGNOSTICS / "phase3_freshness.md").write_text("\n".join(S) + "\n")
    write_json(C.DIAGNOSTICS / "phase3_freshness.json",
               {"generated_utc": utc_now_iso(), "rows": rows})
    log.info("Wrote freshness robustness results")
    print("\n".join(S))


if __name__ == "__main__":
    main()
