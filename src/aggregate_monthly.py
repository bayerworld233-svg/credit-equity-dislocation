"""
Phase 2 — build the firm(permco)-month analysis panel.

Bond side (per permco-month): amount-outstanding-weighted mean of fresh bond ret_eom
  (primary), plus equal-weight and median (robustness), bond count, AO concentration,
  and AO-weighted IG share.
Equity side (per permco-month): one common-equity return. For multi-share-class firms the
  classes are combined by PRIOR-month market cap (no look-ahead); single-class firms use
  their own return.
Panel = inner join on (permco, ym). Forward (t+1) equity and bond returns are attached as
  explicitly-labeled TARGET columns (future realized returns for later dependent-variable
  use; they are NOT used to construct any month-t signal).

Output: data/processed/panel_firm_month.parquet
Run: conda run -n credit-equity python -m src.aggregate_monthly
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()


def build_bond_panel() -> pd.DataFrame:
    bl = pd.read_parquet(C.INTERIM / "bonds_linked.parquet")
    bl["date"] = pd.to_datetime(bl["date"])
    bl["ym"] = bl["date"].dt.to_period("M")
    for c in ["ret_eom", "amount_outstanding"]:
        bl[c] = pd.to_numeric(bl[c], errors="coerce")
    bl["rw"] = bl["ret_eom"] * bl["amount_outstanding"]
    bl["ig_ao"] = (bl["rating_class"] == "0.IG").astype(float) * bl["amount_outstanding"]

    g = bl.groupby(["permco", "ym"])
    bp = g.agg(
        date=("date", "first"),
        bond_ret_ao_num=("rw", "sum"),
        bond_ao_total=("amount_outstanding", "sum"),
        bond_ret_ew=("ret_eom", "mean"),
        bond_ret_med=("ret_eom", "median"),
        n_bonds=("ret_eom", "size"),
        top_ao=("amount_outstanding", "max"),
        ig_ao_num=("ig_ao", "sum"),
    ).reset_index()
    bp["bond_ret_ao"] = bp["bond_ret_ao_num"] / bp["bond_ao_total"]
    bp["top_bond_wt"] = bp["top_ao"] / bp["bond_ao_total"]
    bp["frac_ig_ao"] = bp["ig_ao_num"] / bp["bond_ao_total"]
    return bp.drop(columns=["bond_ret_ao_num", "ig_ao_num", "top_ao"])


def _firm_equity_ret(g: pd.DataFrame) -> float:
    """Prior-cap-weighted mean return for a multi-class permco-month (no look-ahead)."""
    valid = g["mthret"].notna()
    w = g["cap_lag"].where(valid & (g["cap_lag"] > 0))
    if w.notna().any() and w.sum() > 0:
        return float(np.average(g.loc[w.notna(), "mthret"], weights=w.dropna()))
    return float(g.loc[valid, "mthret"].mean())  # fallback: equal weight


def build_equity_panel(permco_keep: set) -> pd.DataFrame:
    e = pd.read_parquet(C.INTERIM / "equity_clean.parquet")
    e = e[e["permco"].isin(permco_keep)].copy()
    e["mthcaldt"] = pd.to_datetime(e["mthcaldt"])
    e["ym"] = e["mthcaldt"].dt.to_period("M")
    for c in ["mthret", "mthcap"]:
        e[c] = pd.to_numeric(e[c], errors="coerce")
    e = e.sort_values(["permno", "ym"])
    e["cap_lag"] = e.groupby("permno")["mthcap"].shift(1)
    e["n_cls"] = e.groupby(["permco", "ym"])["permno"].transform("size")

    # single-class permco-months: direct
    single = e[e["n_cls"] == 1].copy()
    eq_s = single.groupby(["permco", "ym"]).agg(
        equity_ret=("mthret", "first"),
        firm_mktcap=("mthcap", "sum"),
        n_share_classes=("permno", "size"),
    ).reset_index()
    # siccd from (the only) permno
    eq_s = eq_s.merge(single[["permco", "ym", "siccd"]], on=["permco", "ym"], how="left")

    # multi-class permco-months: prior-cap weighted
    multi = e[e["n_cls"] > 1].copy()
    if len(multi):
        ret_m = (multi.groupby(["permco", "ym"]).apply(_firm_equity_ret, include_groups=False)
                 .rename("equity_ret").reset_index())
        cap_m = multi.groupby(["permco", "ym"]).agg(
            firm_mktcap=("mthcap", "sum"), n_share_classes=("permno", "size")).reset_index()
        # siccd from the largest current-cap permno in the group
        idx = multi.sort_values("mthcap").drop_duplicates(["permco", "ym"], keep="last")
        sic_m = idx[["permco", "ym", "siccd"]]
        eq_m = ret_m.merge(cap_m, on=["permco", "ym"]).merge(sic_m, on=["permco", "ym"], how="left")
        eq = pd.concat([eq_s, eq_m], ignore_index=True)
    else:
        eq = eq_s
    return eq


def main() -> None:
    bp = build_bond_panel()
    log.info("bond panel: %s permco-months, %s firms", f"{len(bp):,}", f"{bp['permco'].nunique():,}")

    eq = build_equity_panel(set(bp["permco"].unique()))
    log.info("equity panel: %s permco-months, %s firms", f"{len(eq):,}", f"{eq['permco'].nunique():,}")

    # contemporaneous inner join on (permco, ym): one bond return + one equity return
    panel = bp.merge(eq, on=["permco", "ym"], how="inner")

    # forward (t+1) targets via period shift (no look-ahead: these are future realized returns)
    eq_f = eq[["permco", "ym", "equity_ret"]].copy()
    eq_f["ym"] = eq_f["ym"] - 1
    eq_f = eq_f.rename(columns={"equity_ret": "equity_ret_fwd1"})
    panel = panel.merge(eq_f, on=["permco", "ym"], how="left")

    bf = bp[["permco", "ym", "bond_ret_ao"]].copy()
    bf["ym"] = bf["ym"] - 1
    bf = bf.rename(columns={"bond_ret_ao": "bond_ret_ao_fwd1"})
    panel = panel.merge(bf, on=["permco", "ym"], how="left")

    panel["yyyymm"] = panel["ym"].astype(str).str.replace("-", "").astype(int)
    panel["ym"] = panel["ym"].astype(str)
    panel = panel.sort_values(["ym", "permco"]).reset_index(drop=True)

    cols = ["permco", "ym", "yyyymm", "date", "n_bonds", "bond_ao_total", "top_bond_wt",
            "frac_ig_ao", "bond_ret_ao", "bond_ret_ew", "bond_ret_med",
            "n_share_classes", "firm_mktcap", "siccd", "equity_ret",
            "equity_ret_fwd1", "bond_ret_ao_fwd1"]
    panel = panel[cols]
    panel.to_parquet(C.PROCESSED / "panel_firm_month.parquet", index=False)

    info = {"generated_utc": utc_now_iso(),
            "bond_permco_months": int(len(bp)),
            "equity_permco_months": int(len(eq)),
            "panel_firm_months": int(len(panel)),
            "panel_unique_firms": int(panel["permco"].nunique()),
            "date_min": panel["ym"].min(), "date_max": panel["ym"].max(),
            "bond_only_no_equity": int(len(bp) - len(panel.drop_duplicates(["permco", "ym"]))),
            "with_fwd_equity": int(panel["equity_ret_fwd1"].notna().sum())}
    write_json(C.PROCESSED / "panel_build_log.json", info)
    log.info("Wrote panel: %s firm-months, %s firms, %s..%s",
             f"{len(panel):,}", panel["permco"].nunique(), panel["ym"].min(), panel["ym"].max())


if __name__ == "__main__":
    main()
