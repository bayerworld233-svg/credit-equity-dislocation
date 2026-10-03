"""
Phase 2 — clean the raw CRSP v2 extract into the common-equity sample.

Common-equity filter (approved):
  securitytype = 'EQTY'
  sharetype    = 'NS'
  issuertype in {CORP, REIT}
  mthret not null   (a valid monthly total return; delisting already embedded in mthret)

Keeps permno-level rows (share classes aggregated to permco later). Output:
  data/interim/equity_clean.parquet
Run: conda run -n credit-equity python -m src.clean_equities
"""
from __future__ import annotations

import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()

KEEP = ["permno", "permco", "mthcaldt", "yyyymm", "mthret", "mthcap",
        "mthprc", "siccd", "ticker", "issuernm", "sharetype",
        "securitytype", "issuertype", "primaryexch", "mthdelflg", "mthretflg"]


def main() -> None:
    e = pd.read_parquet(C.RAW / "equity_msf_v2.parquet")
    e["mthcaldt"] = pd.to_datetime(e["mthcaldt"])
    for c in ["mthret", "mthcap"]:
        e[c] = pd.to_numeric(e[c], errors="coerce")

    steps = []

    def record(df, label):
        steps.append({"step": label, "n_rows": int(len(df)),
                      "n_permno": int(df["permno"].nunique()),
                      "n_permco": int(df["permco"].nunique())})
        log.info("%-40s rows=%s permno=%s permco=%s", label,
                 f"{len(df):,}", f"{df['permno'].nunique():,}", f"{df['permco'].nunique():,}")

    record(e, "0. raw msf_v2 (2015-01..2025-12)")
    e = e[e["securitytype"] == "EQTY"];                 record(e, "1. securitytype='EQTY'")
    e = e[e["sharetype"] == "NS"];                      record(e, "2. sharetype='NS'")
    e = e[e["issuertype"].isin(["CORP", "REIT"])];      record(e, "3. issuertype in {CORP,REIT}")
    e = e[e["mthret"].notna()];                         record(e, "4. mthret not null")

    out = e[KEEP].copy()
    out.to_parquet(C.INTERIM / "equity_clean.parquet", index=False)
    write_json(C.INTERIM / "equity_filter_log.json",
               {"generated_utc": utc_now_iso(), "steps": steps})
    log.info("Wrote %s (%s rows)", C.INTERIM / "equity_clean.parquet", f"{len(out):,}")


if __name__ == "__main__":
    main()
