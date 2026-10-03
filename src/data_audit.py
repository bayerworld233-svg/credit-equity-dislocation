"""
Phase 1 data audit. Reads raw parquet from data/raw/, computes diagnostics, and
writes:
  - output/diagnostics/data_audit.md   (human-readable report)
  - output/tables/*.csv                 (supporting tables)
  - output/diagnostics/audit_summary.json

Auditing only: NO aggregation choices, NO signal construction, NO regressions.
The point-in-time link is applied here ONLY to measure mapping quality, not to
build the analysis panel.

Run:  conda run -n credit-equity python -m src.data_audit
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()
PCTS = [0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999]


def _load():
    b = pd.read_parquet(C.RAW / "bondret.parquet")
    l = pd.read_parquet(C.RAW / "bondcrsp_link.parquet")
    e = pd.read_parquet(C.RAW / "equity_msf_v2.parquet")
    f = pd.read_parquet(C.RAW / "ff_factors.parquet")
    for df, col in [(b, "date"), (e, "mthcaldt"), (f, "date")]:
        df[col] = pd.to_datetime(df[col])
    for c in ["trace_startdt", "trace_enddt", "crsp_startdt", "crsp_enddt",
              "link_startdt", "link_enddt"]:
        l[c] = pd.to_datetime(l[c])
    return b, l, e, f


def _missing(df, cols):
    rows = []
    n = len(df)
    for c in cols:
        if c in df.columns:
            miss = int(df[c].isna().sum())
            rows.append({"column": c, "n_missing": miss, "pct_missing": round(100 * miss / n, 3)})
    return pd.DataFrame(rows)


def _quant(df, cols):
    out = {}
    for c in cols:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            d = s.quantile(PCTS).to_dict()
            d.update({"min": s.min(), "max": s.max(), "mean": s.mean(), "n": int(s.size)})
            out[c] = d
    return pd.DataFrame(out).T


def md_table(df, floatfmt="{:.6g}"):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda x: floatfmt.format(x) if pd.notna(x) else "")
    return df.to_markdown(index=True)


def main():
    b, l, e, f = _load()
    S = []  # markdown lines
    J = {"generated_utc": utc_now_iso()}
    W = lambda *x: S.append(" ".join(str(i) for i in x))

    W(f"# Phase 1 Data Audit\n\nGenerated: {utc_now_iso()}\n")
    W("Raw sources (see `data/raw/_manifest.json` for SQL + hashes):\n")
    W(f"- bondret: **{len(b):,}** rows | equity_msf_v2: **{len(e):,}** | "
      f"bondcrsp_link: **{len(l):,}** | ff_factors: **{len(f):,}**\n")

    # ===================== BONDRET =====================
    W("\n## 1. Corporate bonds — `wrdsapps_bondret.bondret`\n")
    W(f"- Date range: **{b['date'].min().date()} → {b['date'].max().date()}**")
    W(f"- Unique bond CUSIPs: **{b['cusip'].nunique():,}** | "
      f"unique issuers (`company_symbol`): **{b['company_symbol'].nunique():,}**")
    dup_bd = int(b.duplicated(subset=["cusip", "date"]).sum())
    W(f"- Duplicate (cusip, date) rows: **{dup_bd}** (expected key = cusip×date)")
    J["bondret"] = {"n_rows": len(b), "n_bonds": int(b["cusip"].nunique()),
                    "n_issuers": int(b["company_symbol"].nunique()),
                    "dup_cusip_date": dup_bd}

    miss_b = _missing(b, ["ret_eom", "ret_ldm", "ret_l5m", "price_eom", "yield",
                          "t_spread", "coupon", "duration", "tmt", "amount_outstanding",
                          "rating_num", "rating_class", "rating_cat", "maturity"])
    miss_b.to_csv(C.TABLES / "bond_missingness.csv", index=False)
    W("\n**Missingness (key columns):**\n")
    W(md_table(miss_b.set_index("column")))

    W("\n**Units / distribution of key numeric variables** "
      "(infer units from magnitudes):\n")
    q_b = _quant(b, ["ret_eom", "yield", "t_spread", "coupon", "duration", "tmt",
                     "amount_outstanding", "price_eom", "rating_num"])
    q_b.to_csv(C.TABLES / "bond_distributions.csv")
    W(md_table(q_b))

    # Extreme returns
    r = pd.to_numeric(b["ret_eom"], errors="coerce")
    for thr in [0.5, 1.0, 2.0]:
        W(f"- |ret_eom| > {thr:.0%}: **{int((r.abs() > thr).sum()):,}** obs "
          f"({100*(r.abs()>thr).mean():.4f}%)")
    J["bondret"]["ret_eom_abs_gt_1"] = int((r.abs() > 1.0).sum())

    # Ratings composition
    W("\n**rating_class composition (IG/HY split):**\n")
    rc = b["rating_class"].value_counts(dropna=False).rename_axis("rating_class").reset_index(name="n")
    rc["pct"] = (100 * rc["n"] / len(b)).round(2)
    rc.to_csv(C.TABLES / "bond_rating_class.csv", index=False)
    W(md_table(rc.set_index("rating_class")))

    # Bonds per issuer-month (raw, via company_symbol)
    bpf = b.groupby(["company_symbol", "date"]).size()
    W("\n**Bonds per issuer-month (raw, by `company_symbol`):**")
    W(f"- mean {bpf.mean():.2f}, median {int(bpf.median())}, "
      f"p90 {int(bpf.quantile(.9))}, p99 {int(bpf.quantile(.99))}, max {int(bpf.max())}")
    J["bondret"]["bonds_per_issuer_month_median"] = float(bpf.median())
    J["bondret"]["bonds_per_issuer_month_max"] = int(bpf.max())

    # ---- 1b. Price staleness & data quality (KEY FINDING) ----
    W("\n### 1b. Price staleness & characteristic data quality (key finding)\n")
    ret = pd.to_numeric(b["ret_eom"], errors="coerce")
    is_zero = (ret == 0)
    is_cry = (b["price_eom_flg"] == "CryFwd")
    W(f"- `price_eom_flg`: **Current {int((~is_cry).sum()):,}** "
      f"({100*(~is_cry).mean():.1f}%) vs **CryFwd (carried-forward/stale) "
      f"{int(is_cry.sum()):,}** ({100*is_cry.mean():.1f}%)")
    W(f"- `ret_eom` exactly == 0: **{int(is_zero.sum()):,}** "
      f"({100*is_zero.mean():.1f}% of all rows)")
    W(f"- Zero-return rate | CryFwd = **{100*is_zero[is_cry].mean():.1f}%** vs | "
      f"Current = **{100*is_zero[~is_cry].mean():.2f}%** "
      f"(→ the zero-return mass is stale carried-forward prices)")

    # staleness & quality by bond_type
    bt = (b.assign(ret=ret, is_zero=is_zero, is_cry=is_cry)
            .groupby("bond_type")
            .agg(n=("ret", "size"),
                 pct_rows=("ret", lambda s: round(100*len(s)/len(b), 2)),
                 cryfwd_rate=("is_cry", lambda s: round(100*s.mean(), 1)),
                 zero_ret_rate=("is_zero", lambda s: round(100*s.mean(), 1)),
                 ret_na_rate=("ret", lambda s: round(100*s.isna().mean(), 1)))
            .sort_values("n", ascending=False))
    bt.to_csv(C.TABLES / "bond_type_staleness.csv")
    W("\n**Staleness & missingness by `bond_type`** "
      "(CDEB=debentures, CMTZ=medium-term notes, CMTN=MTN):\n")
    W(md_table(bt))

    # implausible characteristic values
    y = pd.to_numeric(b["yield"], errors="coerce")
    dur = pd.to_numeric(b["duration"], errors="coerce")
    amt = pd.to_numeric(b["amount_outstanding"], errors="coerce")
    cpn = pd.to_numeric(b["coupon"], errors="coerce")
    W("\n**Characteristic data-quality flags (counts of implausible values):**")
    W(f"- `yield` (decimal units; median {y[(y>=0)&(y<=.3)].median():.4f}): "
      f"**{int((y<0).sum()):,} negative** ({100*(y<0).mean():.1f}%), "
      f"**{int((y>1).sum()):,} > 100%**, max = {y.max():.3g} (CORRUPT — field unreliable)")
    W(f"- `duration` (years): {int((dur>40).sum()):,} > 40yr, {int((dur>100).sum()):,} > 100 "
      f"(max {dur.max():.3g}); **{100*((dur>=0)&(dur<=40)).mean():.2f}% plausible [0,40]**")
    W(f"- `amount_outstanding` ($thousands): {int((amt<0).sum()):,} negative, "
      f"{int((amt==0).sum()):,} zero (minor)")
    W(f"- `coupon`: {100*(cpn==0).mean():.1f}% == 0, almost all `bond_type=CMTZ` "
      f"(zero/structured MTNs)")
    J["bondret"]["cryfwd_rate_pct"] = round(100*is_cry.mean(), 2)
    J["bondret"]["zero_ret_pct"] = round(100*is_zero.mean(), 2)
    J["bondret"]["yield_negative_pct"] = round(100*(y < 0).mean(), 2)

    # Monthly coverage table
    mcov = (b.groupby(b["date"].dt.to_period("M"))
              .agg(n_bond_obs=("cusip", "size"),
                   n_ret=("ret_eom", lambda s: int(s.notna().sum())),
                   n_bonds=("cusip", "nunique"))
              .reset_index())
    mcov["date"] = mcov["date"].astype(str)
    mcov.to_csv(C.TABLES / "bond_monthly_coverage.csv", index=False)

    # ===================== EQUITY =====================
    W("\n\n## 2. Equities — `crsp.msf_v2` (CRSP v2 monthly)\n")
    W(f"- Date range: **{e['mthcaldt'].min().date()} → {e['mthcaldt'].max().date()}**")
    W(f"- Unique permno: **{e['permno'].nunique():,}** | permco: **{e['permco'].nunique():,}**")
    dup_pm = int(e.duplicated(subset=["permno", "mthcaldt"]).sum())
    W(f"- Duplicate (permno, mthcaldt) rows: **{dup_pm}**")
    J["equity"] = {"n_rows": len(e), "n_permno": int(e["permno"].nunique()),
                   "dup_permno_date": dup_pm}

    miss_e = _missing(e, ["mthret", "mthretx", "mthcap", "mthprc", "shrout",
                          "siccd", "cusip", "mthvol"])
    miss_e.to_csv(C.TABLES / "equity_missingness.csv", index=False)
    W("\n**Missingness (key columns):**\n")
    W(md_table(miss_e.set_index("column")))

    q_e = _quant(e, ["mthret", "mthretx", "mthprc", "mthcap", "shrout", "mthvol"])
    q_e.to_csv(C.TABLES / "equity_distributions.csv")
    W("\n**Units / distribution:**\n")
    W(md_table(q_e))

    # negative prices (CRSP bid/ask-average convention)
    negp = int((pd.to_numeric(e["mthprc"], errors="coerce") < 0).sum())
    W(f"\n- Negative `mthprc` values (CRSP bid/ask-avg convention): **{negp:,}** "
      f"({100*negp/len(e):.3f}%)")

    # extreme equity returns
    er = pd.to_numeric(e["mthret"], errors="coerce")
    for thr in [0.5, 1.0, 2.0]:
        W(f"- |mthret| > {thr:.0%}: **{int((er.abs()>thr).sum()):,}** "
          f"({100*(er.abs()>thr).mean():.4f}%)")

    # delisting flag + share/security/issuer type composition
    W("\n**`mthdelflg` (delisting flag) composition:**\n")
    dfl = e["mthdelflg"].value_counts(dropna=False).rename_axis("mthdelflg").reset_index(name="n")
    W(md_table(dfl.set_index("mthdelflg")))
    for col in ["sharetype", "securitytype", "issuertype"]:
        W(f"\n**`{col}` composition:**\n")
        vc = e[col].value_counts(dropna=False).rename_axis(col).reset_index(name="n")
        vc["pct"] = (100 * vc["n"] / len(e)).round(2)
        vc.to_csv(C.TABLES / f"equity_{col}.csv", index=False)
        W(md_table(vc.set_index(col)))
    W("\n**`mthretflg` composition (return availability/missing-code):**\n")
    rfl = e["mthretflg"].value_counts(dropna=False).rename_axis("mthretflg").reset_index(name="n")
    rfl.to_csv(C.TABLES / "equity_mthretflg.csv", index=False)
    W(md_table(rfl.set_index("mthretflg")))

    # ===================== LINK TABLE =====================
    W("\n\n## 3. Official bond↔CRSP link — `wrdsapps_link_crsp_bond.bondcrsp_link`\n")
    W(f"- Rows: **{len(l):,}** | unique bond CUSIP: **{l['cusip'].nunique():,}** | "
      f"unique permno: **{l['permno'].nunique():,}** | permco: **{l['permco'].nunique():,}**")
    W(f"- link_startdt range: {l['link_startdt'].min().date()} → {l['link_startdt'].max().date()}; "
      f"link_enddt max: {l['link_enddt'].max().date()}")
    # bonds mapping to multiple permno across history
    multi = l.groupby("cusip")["permno"].nunique()
    W(f"- Bond CUSIPs mapping to >1 permno across history: "
      f"**{int((multi>1).sum()):,}** ({100*(multi>1).mean():.2f}%)")
    J["link"] = {"n_rows": len(l), "n_bond_cusip": int(l["cusip"].nunique()),
                 "n_permno": int(l["permno"].nunique()),
                 "bonds_multi_permno": int((multi > 1).sum())}

    # ===================== MAPPING QUALITY =====================
    W("\n\n## 4. Mapping quality: bondret → permno (point-in-time)\n")
    # merge bond obs to link on cusip, filter to date within [link_startdt, link_enddt]
    bl = b[["cusip", "date", "company_symbol", "ret_eom"]].merge(
        l[["cusip", "permno", "permco", "link_startdt", "link_enddt"]],
        on="cusip", how="left")
    in_win = (bl["date"] >= bl["link_startdt"]) & (bl["date"] <= bl["link_enddt"])
    bl_matched = bl[in_win].copy()
    # a bond-month is "linked" if it has >=1 valid permno
    key = ["cusip", "date"]
    linked_keys = bl_matched.drop_duplicates(key)[key]
    n_bondmonths = len(b.drop_duplicates(key))
    n_linked = len(linked_keys)
    W(f"- Bond-months total: **{n_bondmonths:,}**; linked to >=1 permno: "
      f"**{n_linked:,}** (**{100*n_linked/n_bondmonths:.2f}%**)")
    # ambiguous: bond-month matching >1 distinct permno simultaneously
    amb = bl_matched.groupby(key)["permno"].nunique()
    n_amb = int((amb > 1).sum())
    W(f"- Ambiguous bond-months (match >1 permno at once): **{n_amb:,}** "
      f"({100*n_amb/max(n_linked,1):.3f}% of linked)")
    # bond cusips never linked at all
    never = ~b["cusip"].isin(bl_matched["cusip"].unique())
    W(f"- Bond CUSIPs never linked in-window: "
      f"**{b.loc[never,'cusip'].nunique():,}** of {b['cusip'].nunique():,}")
    J["mapping"] = {"bond_months": int(n_bondmonths), "linked": int(n_linked),
                    "link_rate_pct": round(100*n_linked/n_bondmonths, 3),
                    "ambiguous_bond_months": n_amb}

    # match rate by year
    bl_matched["year"] = bl_matched["date"].dt.year
    b["year"] = b["date"].dt.year
    by_year = []
    for yr in sorted(b["year"].unique()):
        tot = b[b["year"] == yr].drop_duplicates(key).shape[0]
        lk = bl_matched[bl_matched["year"] == yr].drop_duplicates(key).shape[0]
        by_year.append({"year": int(yr), "bond_months": tot, "linked": lk,
                        "link_rate_pct": round(100*lk/tot, 2)})
    by_year = pd.DataFrame(by_year)
    by_year.to_csv(C.TABLES / "mapping_link_rate_by_year.csv", index=False)
    W("\n**Link rate by year:**\n")
    W(md_table(by_year.set_index("year")))

    # firms (permno) per month and bonds per firm-month (via link, unambiguous mapping)
    # take first permno per bond-month (for structure counting only; NOT a modeling choice)
    bm = bl_matched.sort_values(key + ["permno"]).drop_duplicates(key)
    firms_per_month = bm.groupby("date")["permno"].nunique()
    bonds_per_firm_month = bm.groupby(["permno", "date"]).size()
    W(f"\n- Linked firms per month: mean **{firms_per_month.mean():.0f}**, "
      f"min {int(firms_per_month.min())}, max {int(firms_per_month.max())}")
    W(f"- Bonds per firm-month (linked): mean {bonds_per_firm_month.mean():.2f}, "
      f"median {int(bonds_per_firm_month.median())}, p90 {int(bonds_per_firm_month.quantile(.9))}, "
      f"p99 {int(bonds_per_firm_month.quantile(.99))}, max {int(bonds_per_firm_month.max())}")
    J["mapping"]["firms_per_month_mean"] = float(firms_per_month.mean())
    J["mapping"]["bonds_per_firm_month_median"] = float(bonds_per_firm_month.median())

    fpm = firms_per_month.reset_index()
    fpm.columns = ["date", "n_firms"]
    fpm["date"] = fpm["date"].astype(str)
    fpm.to_csv(C.TABLES / "linked_firms_per_month.csv", index=False)

    bpfm_dist = bonds_per_firm_month.value_counts().sort_index().reset_index()
    bpfm_dist.columns = ["bonds_in_firm_month", "n_firm_months"]
    bpfm_dist.to_csv(C.TABLES / "bonds_per_firm_month_dist.csv", index=False)

    # ---- 4b. Usable firm cross-section under candidate universe restrictions ----
    # DIAGNOSTIC ONLY — not a chosen filter. Shows that dropping stale notes keeps firms.
    W("\n### 4b. Firm cross-section under candidate universe restrictions (diagnostic)\n")
    W("_Shows how the linked **firm** cross-section holds up when stale/illiquid "
      "bonds are excluded. Evidence for a Phase-2 decision, not a filter chosen here._\n")

    def _universe_row(mask, label):
        bs = b[mask]
        m = bs[["cusip", "date"]].merge(
            l[["cusip", "permno", "link_startdt", "link_enddt"]], on="cusip", how="left")
        m = m[(m["date"] >= m["link_startdt"]) & (m["date"] <= m["link_enddt"])]
        m = m.sort_values(["cusip", "date", "permno"]).drop_duplicates(["cusip", "date"])
        fpm = m.groupby("date")["permno"].nunique()
        bpf = m.groupby(["permno", "date"]).size()
        return {"universe": label, "bond_months": len(bs),
                "linked_bond_months": len(m),
                "firms_per_month_mean": round(fpm.mean()),
                "firms_per_month_min": int(fpm.min()),
                "bonds_per_firm_mean": round(bpf.mean(), 1),
                "bonds_per_firm_median": int(bpf.median())}

    uni = pd.DataFrame([
        _universe_row(b["cusip"].notna(), "ALL (raw)"),
        _universe_row(b["price_eom_flg"] == "Current", "Current price only"),
        _universe_row(b["bond_type"] == "CDEB", "CDEB only"),
        _universe_row((b["price_eom_flg"] == "Current") & (b["bond_type"] == "CDEB"),
                      "Current + CDEB"),
    ]).set_index("universe")
    uni.to_csv(C.TABLES / "candidate_universe_sizes.csv")
    W(md_table(uni))
    J["candidate_universes"] = uni.reset_index().to_dict(orient="records")

    # ===================== FF =====================
    W("\n\n## 5. Fama-French factors — `ff.factors_monthly`\n")
    W(f"- Date range: {f['date'].min().date()} → {f['date'].max().date()}; "
      f"rows: {len(f)} (cols: {', '.join(f.columns)})")

    # write report
    report = "\n".join(S) + "\n"
    (C.DIAGNOSTICS / "data_audit.md").write_text(report)
    write_json(C.DIAGNOSTICS / "audit_summary.json", J)
    log.info("Wrote %s", C.DIAGNOSTICS / "data_audit.md")
    log.info("Wrote %s supporting tables to %s", len(list(C.TABLES.glob('*.csv'))), C.TABLES)
    print("\n" + report)


if __name__ == "__main__":
    main()
