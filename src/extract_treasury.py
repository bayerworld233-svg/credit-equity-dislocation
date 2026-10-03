"""
Phase 3 robustness — reproducible extract of the CRSP Fixed-Term Treasury indices.

Pulls the 7 nominal constant-maturity points (1,2,5,7,10,20,30y) from
crsp_a_treasuries.tfz_mth_ft to data/raw/treasury_ft.parquet (+ manifest).
Units (verified via pg_description / sample): tmretadj = percent, tmytm = percent,
tmduratn = DAYS. Stored raw (unconverted); conversions happen downstream.

Run: conda run -n credit-equity python -m src.extract_treasury
"""
from __future__ import annotations

from . import config as C
from .utils import file_sha256, get_logger, utc_now_iso, write_json

log = get_logger()

KY = {2000003: "1Y", 2000004: "2Y", 2000005: "5Y", 2000006: "7Y",
      2000007: "10Y", 2000008: "20Y", 2000009: "30Y"}

SQL = f"""
SELECT kytreasnox, mcaldt, tmyearstm, tmduratn, tmretadj, tmytm
FROM crsp_a_treasuries.tfz_mth_ft
WHERE kytreasnox IN ({",".join(str(k) for k in KY)})
  AND mcaldt BETWEEN '{C.EQUITY_START}' AND '{C.EQUITY_END}'
"""


def main():
    db = C.get_connection()
    try:
        df = db.raw_sql(SQL)
    finally:
        db.close()
    df["term_label"] = df["kytreasnox"].map(KY)
    out = C.RAW / "treasury_ft.parquet"
    df.to_parquet(out, index=False)
    write_json(C.RAW / "_manifest_treasury.json", {
        "extraction_utc": utc_now_iso(), "source_table": "crsp_a_treasuries.tfz_mth_ft",
        "sql": " ".join(SQL.split()), "n_rows": int(len(df)),
        "terms": list(KY.values()),
        "units": {"tmretadj": "percent", "tmytm": "percent", "tmduratn": "days"},
        "file": str(out.relative_to(C.ROOT)), "sha256": file_sha256(out),
    })
    log.info("Wrote %s (%s rows, %s terms, %s..%s)", out.name, f"{len(df):,}",
             df["kytreasnox"].nunique(), df["mcaldt"].min(), df["mcaldt"].max())


if __name__ == "__main__":
    main()
