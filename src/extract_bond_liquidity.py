"""
Phase 3 robustness — reproducible supplementary extract of bond price-timing / liquidity
fields not pulled in Phase 1, for the primary universe (Current, conv=0, CDEB/CMTN).

Fields: t_date (price-setting trade date), t_volume, t_dvolume, gap. Keyed (cusip, date).
Only t_date is used in the freshness test; the rest are stored for later approved tests.

Output: data/raw/bond_liquidity.parquet (+ _manifest_bond_liquidity.json)
Run: conda run -n credit-equity python -m src.extract_bond_liquidity
"""
from __future__ import annotations

from . import config as C
from .utils import file_sha256, get_logger, utc_now_iso, write_json

log = get_logger()

SQL = f"""
SELECT cusip, date, t_date, t_volume, t_dvolume, gap
FROM wrdsapps_bondret.bondret
WHERE price_eom_flg='Current' AND conv=0 AND bond_type IN ('CDEB','CMTN')
  AND date BETWEEN '{C.BOND_START}' AND '{C.BOND_END}'
  AND ret_eom IS NOT NULL
"""


def main():
    db = C.get_connection()
    try:
        df = db.raw_sql(SQL)
    finally:
        db.close()
    out = C.RAW / "bond_liquidity.parquet"
    df.to_parquet(out, index=False)
    write_json(C.RAW / "_manifest_bond_liquidity.json", {
        "extraction_utc": utc_now_iso(), "source_table": "wrdsapps_bondret.bondret",
        "sql": " ".join(SQL.split()), "n_rows": int(len(df)),
        "note": "t_date=price-setting TRACE trade execution date; used for month-end freshness.",
        "file": str(out.relative_to(C.ROOT)), "sha256": file_sha256(out)})
    log.info("Wrote %s (%s rows)", out.name, f"{len(df):,}")


if __name__ == "__main__":
    main()
