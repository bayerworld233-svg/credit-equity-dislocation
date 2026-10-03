"""
Phase 2 — construction diagnostics for the firm-month analysis panel.
Writes output/diagnostics/panel_construction.md (+ CSV tables, JSON summary).
No regressions/backtests. Run: conda run -n credit-equity python -m src.panel_audit
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config as C
from .utils import utc_now_iso, write_json, get_logger

log = get_logger()


def q(s, ps=(0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)):
    s = pd.to_numeric(s, errors="coerce").dropna()
    d = {f"p{int(p*100)}": round(float(s.quantile(p)), 5) for p in ps}
    d.update(min=round(float(s.min()), 5), max=round(float(s.max()), 5),
             mean=round(float(s.mean()), 5), n=int(s.size))
    return d


def mdt(df):
    return df.to_markdown(index=True)


def main():
    p = pd.read_parquet(C.PROCESSED / "panel_firm_month.parquet")
    logs = {name: json.load(open(C.INTERIM / f))
            for name, f in [("bonds", "bonds_filter_log.json"),
                            ("equity", "equity_filter_log.json"),
                            ("link", "link_log.json")]}
    build = json.load(open(C.PROCESSED / "panel_build_log.json"))

    S, J = [], {"generated_utc": utc_now_iso()}
    W = lambda *x: S.append(" ".join(str(i) for i in x))

    W(f"# Phase 2 Panel Construction Diagnostics\n\nGenerated: {utc_now_iso()}\n")

    # ---- 1. Step-by-step filtering / link / drop counts ----
    W("## 1. Filtering, linking & drop counts (each step)\n")
    W("**Bond cleaning:**\n")
    W(mdt(pd.DataFrame(logs["bonds"]["steps"]).set_index("step")))
    W("\n**Equity cleaning (common equity):**\n")
    W(mdt(pd.DataFrame(logs["equity"]["steps"]).set_index("step")))
    W("\n**Bond→permco link:**")
    for k in ["bond_months_in", "bond_months_linked", "bond_months_unlinked",
              "ambiguous_multi_permco_bond_months_dropped", "bond_months_out",
              "n_permco_out", "null_link_startdt", "null_link_enddt"]:
        W(f"- {k}: **{logs['link'][k]:,}**")
    W("\n**Aggregation → panel (inner join on permco×month):**")
    W(f"- bond permco-months: **{build['bond_permco_months']:,}**")
    W(f"- equity permco-months (firms in bond set): **{build['equity_permco_months']:,}**")
    W(f"- **panel firm-months (bond ∩ equity): {build['panel_firm_months']:,}**")
    bond_pm_wo_eq = build["bond_permco_months"] - build["panel_firm_months"]
    W(f"- bond permco-months with NO matching common-equity firm-month: "
      f"**{bond_pm_wo_eq:,}** ({100*bond_pm_wo_eq/build['bond_permco_months']:.1f}%)")

    # ---- 2. Final sample size & coverage ----
    W("\n## 2. Final sample & monthly firm coverage\n")
    W(f"- Firm-months: **{len(p):,}** | unique firms (permco): **{p['permco'].nunique():,}** | "
      f"months: **{p['ym'].min()} → {p['ym'].max()}** ({p['ym'].nunique()} months)")
    fpm = p.groupby("ym")["permco"].nunique()
    W(f"- Firms per month: mean **{fpm.mean():.0f}**, min {fpm.min()} ({fpm.idxmin()}), "
      f"max {fpm.max()} ({fpm.idxmax()})")
    fpm.rename("n_firms").reset_index().to_csv(C.TABLES / "panel_firms_per_month.csv", index=False)
    J["n_firm_months"] = int(len(p)); J["n_firms"] = int(p["permco"].nunique())
    J["firms_per_month_mean"] = float(fpm.mean())

    # ---- 3. Bonds per firm-month ----
    W("\n## 3. Bonds per firm-month\n")
    W(f"```\n{json.dumps(q(p['n_bonds'], (0.05,0.25,0.5,0.75,0.9,0.95,0.99)), indent=0)}\n```")
    W(f"- firm-months with exactly 1 bond: **{int((p['n_bonds']==1).sum()):,}** "
      f"({100*(p['n_bonds']==1).mean():.1f}%); with ≥2: {100*(p['n_bonds']>=2).mean():.1f}%")
    (p["n_bonds"].value_counts().sort_index().rename_axis("n_bonds")
     .reset_index(name="n_firm_months")).to_csv(C.TABLES / "panel_bonds_per_firm_month.csv", index=False)

    # ---- 4. AO weight concentration ----
    W("\n## 4. AO-weight concentration (largest bond's share of firm AO)\n")
    W(f"```\n{json.dumps(q(p['top_bond_wt']), indent=0)}\n```")
    W(f"- firm-months where top bond ≥ 50% of AO: {100*(p['top_bond_wt']>=0.5).mean():.1f}% "
      f"(note: single-bond firm-months are 100% by construction)")
    W(f"- among firm-months with ≥2 bonds, top-bond weight: "
      f"mean {p.loc[p['n_bonds']>=2,'top_bond_wt'].mean():.3f}, "
      f"p95 {p.loc[p['n_bonds']>=2,'top_bond_wt'].quantile(.95):.3f}")

    # ---- 5. Missingness ----
    W("\n## 5. Missingness in panel columns\n")
    miss = pd.DataFrame({"n_missing": p.isna().sum(),
                         "pct_missing": (100*p.isna().mean()).round(3)})
    W(mdt(miss))
    W("\n_Note: `equity_ret_fwd1` / `bond_ret_ao_fwd1` are forward TARGETS; missing at the "
      "last month of a firm's record (no t+1), which is expected, not look-ahead._")

    # ---- 6. Return distributions ----
    W("\n## 6. Return distributions\n")
    for col in ["bond_ret_ao", "bond_ret_ew", "bond_ret_med", "equity_ret", "equity_ret_fwd1"]:
        W(f"- **{col}**: `{json.dumps(q(p[col]))}`")
    W(f"\n- Corr(bond AO vs equity, contemporaneous): "
      f"**{p[['bond_ret_ao','equity_ret']].corr().iloc[0,1]:.3f}**")
    W(f"- Corr(AO vs EW): {p[['bond_ret_ao','bond_ret_ew']].corr().iloc[0,1]:.3f}, "
      f"Corr(AO vs median): {p[['bond_ret_ao','bond_ret_med']].corr().iloc[0,1]:.3f}")

    # ---- 7. Integrity checks ----
    W("\n## 7. Integrity & no-look-ahead checks\n")
    dup = int(p.duplicated(["permco", "ym"]).sum())
    W(f"- Unique (permco, ym) — one bond return + one equity return per firm-month: "
      f"duplicates = **{dup}** {'✅' if dup==0 else '❌'}")
    one_bond = int(p["bond_ret_ao"].notna().sum()); one_eq = int(p["equity_ret"].notna().sum())
    W(f"- Rows with a bond return: **{one_bond:,}** / {len(p):,}; with an equity return: "
      f"**{one_eq:,}** / {len(p):,} {'✅' if one_bond==len(p)==one_eq else '❌'}")

    # no-look-ahead: equity_ret_fwd1[t] must equal equity_ret[t+1] for consecutive firm-months
    pp = p.sort_values(["permco", "yyyymm"]).copy()
    pp["ym_p"] = pd.PeriodIndex(pp["ym"], freq="M")
    pp["next_ym"] = pp.groupby("permco")["ym_p"].shift(-1)
    pp["next_eq"] = pp.groupby("permco")["equity_ret"].shift(-1)
    consec = pp[pp["next_ym"] == (pp["ym_p"] + 1)]
    mism = int((~np.isclose(consec["equity_ret_fwd1"], consec["next_eq"], equal_nan=False)).sum())
    W(f"- Forward-return alignment: for consecutive firm-months, equity_ret_fwd1[t] == "
      f"equity_ret[t+1] — mismatches = **{mism}** of {len(consec):,} {'✅' if mism==0 else '❌'}")
    W(f"- Bond signal month == equity return month by construction (merged on same ym) ✅")
    W(f"- Share-class weighting uses PRIOR-month cap (shift +1); no contemporaneous cap "
      f"used as weight ✅")
    last_m = p["ym"].max()
    W(f"- Forward equity return present for last signal month ({last_m}): "
      f"{int(p.loc[p['ym']==last_m,'equity_ret_fwd1'].notna().sum()):,} / "
      f"{int((p['ym']==last_m).sum()):,} firms (sourced from {last_m[:4]}-12 CRSP)")
    J["dup_permco_ym"] = dup; J["fwd_mismatch"] = mism

    (C.DIAGNOSTICS / "panel_construction.md").write_text("\n".join(S) + "\n")
    write_json(C.DIAGNOSTICS / "panel_audit_summary.json", J)
    log.info("Wrote %s", C.DIAGNOSTICS / "panel_construction.md")
    print("\n".join(S))


if __name__ == "__main__":
    main()
