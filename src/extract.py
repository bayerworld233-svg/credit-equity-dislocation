"""
Reproducible WRDS extraction for the Credit-Equity Dislocation project (Phase 1).

Pulls four raw datasets to data/raw/ as parquet and writes data/raw/_manifest.json
recording source table, exact SQL, extraction time, row/column counts, key uniques,
file hash, and size. RAW EXTRACTS ARE NEVER MODIFIED after this step.

Run:  conda run -n credit-equity python -m src.extract
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config as C
from .utils import file_sha256, get_logger, utc_now_iso, write_json

log = get_logger()

# ----------------------------------------------------------------------------
# Exact SQL (kept inline for reproducibility; mirrors the Phase 0 approved spec)
# ----------------------------------------------------------------------------
SQL_BONDS = f"""
SELECT date, cusip, company_symbol, isin, bond_sym_id, issue_id,
       ret_eom, ret_ldm, ret_l5m, price_eom, price_eom_flg,
       yield, t_spread, t_yld_pt, coupon,
       offering_date, offering_amt, principal_amt, amount_outstanding,
       maturity, tmt, duration, remcoups,
       r_sp, r_mr, r_fr, rating_num, rating_cat, rating_class,
       bond_type, security_level, conv, defaulted, default_date
FROM {C.TBL_BONDRET}
WHERE date BETWEEN '{C.BOND_START}' AND '{C.BOND_END}'
"""

SQL_LINK = f"""
SELECT cusip, permno, permco,
       trace_startdt, trace_enddt, crsp_startdt, crsp_enddt,
       link_startdt, link_enddt
FROM {C.TBL_BONDCRSP_LINK}
"""

SQL_EQUITY = f"""
SELECT permno, permco, mthcaldt, yyyymm,
       mthret, mthretx, mthretflg, mthdelflg,
       mthcap, mthprc, mthprcflg, mthvol, shrout,
       siccd, cusip, ticker, issuernm,
       sharetype, securitytype, securitysubtype, issuertype,
       primaryexch, exchangetier, tradingstatusflg, conditionaltype
FROM {C.TBL_EQUITY}
WHERE mthcaldt BETWEEN '{C.EQUITY_START}' AND '{C.EQUITY_END}'
"""

SQL_FF = f"""
SELECT date, mktrf, smb, hml, umd, rf
FROM {C.TBL_FF}
WHERE date BETWEEN '{C.EQUITY_START}' AND '{C.EQUITY_END}'
"""

JOBS = {
    "bondret": dict(sql=SQL_BONDS, source=C.TBL_BONDRET,
                    uniq=["cusip", "company_symbol"], window=(C.BOND_START, C.BOND_END)),
    "bondcrsp_link": dict(sql=SQL_LINK, source=C.TBL_BONDCRSP_LINK,
                          uniq=["cusip", "permno", "permco"], window=(None, None)),
    "equity_msf_v2": dict(sql=SQL_EQUITY, source=C.TBL_EQUITY,
                          uniq=["permno", "permco"], window=(C.EQUITY_START, C.EQUITY_END)),
    "ff_factors": dict(sql=SQL_FF, source=C.TBL_FF,
                       uniq=[], window=(C.EQUITY_START, C.EQUITY_END)),
}


def main() -> None:
    db = C.get_connection()
    log.info("Connected to WRDS as %s", C.resolve_wrds_username())
    manifest = {"extraction_utc": utc_now_iso(), "datasets": {}}

    try:
        for name, job in JOBS.items():
            log.info("Extracting %s from %s ...", name, job["source"])
            df = db.raw_sql(job["sql"])
            out = C.RAW / f"{name}.parquet"
            df.to_parquet(out, index=False)

            entry = {
                "source_table": job["source"],
                "requested_window": {"start": job["window"][0], "end": job["window"][1]},
                "sql": " ".join(job["sql"].split()),
                "n_rows": int(len(df)),
                "n_cols": int(df.shape[1]),
                "columns": list(df.columns),
                "file": str(out.relative_to(C.ROOT)),
                "sha256": file_sha256(out),
                "bytes": out.stat().st_size,
            }
            for col in job["uniq"]:
                if col in df.columns:
                    entry[f"n_unique_{col}"] = int(df[col].nunique(dropna=True))
            manifest["datasets"][name] = entry
            log.info("  -> %s rows, %s cols, saved %s",
                     f"{len(df):,}", df.shape[1], out.name)
    finally:
        db.close()

    write_json(C.RAW / "_manifest.json", manifest)
    log.info("Wrote manifest: %s", (C.RAW / "_manifest.json"))
    log.info("Phase 1 extraction complete.")


if __name__ == "__main__":
    main()
