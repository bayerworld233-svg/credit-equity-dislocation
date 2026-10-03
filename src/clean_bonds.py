"""
Phase 2 — clean the raw bond extract into the PRIMARY bond-return sample.

Primary eligibility (approved; duration is NOT an eligibility filter):
  price_eom_flg = 'Current'  (fresh, non-stale month-end price)
  conv = 0                   (exclude convertibles)
  bond_type in {CDEB, CMTN}  (US corporate debentures + MTNs; exclude CMTZ zeros, CP)
  ret_eom not null           (a valid monthly return is the signal input)
  amount_outstanding > 0     (AO is the aggregation weight — intrinsic to construction)

Every step's row count is logged (no silent drops). Output: data/interim/bonds_clean.parquet.
Run: conda run -n credit-equity python -m src.clean_bonds
"""
from __future__ import annotations

import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()

KEEP = ["date", "cusip", "company_symbol", "bond_type", "security_level",
        "ret_eom", "price_eom_flg", "amount_outstanding", "coupon",
        "maturity", "tmt", "duration", "yield", "t_spread",
        "rating_num", "rating_cat", "rating_class", "defaulted"]


def main() -> None:
    b = pd.read_parquet(C.RAW / "bondret.parquet")
    b["date"] = pd.to_datetime(b["date"])
    for c in ["ret_eom", "amount_outstanding", "conv"]:
        b[c] = pd.to_numeric(b[c], errors="coerce")

    steps = []

    def record(df, label):
        steps.append({"step": label, "n_rows": int(len(df)),
                      "n_bonds": int(df["cusip"].nunique()),
                      "n_bond_months": int(df.drop_duplicates(["cusip", "date"]).shape[0])})
        log.info("%-34s rows=%s bonds=%s", label, f"{len(df):,}", f"{df['cusip'].nunique():,}")

    record(b, "0. raw bondret (2015-01..2025-11)")
    b = b[b["price_eom_flg"] == "Current"];           record(b, "1. price_eom_flg='Current'")
    b = b[b["conv"] == 0];                              record(b, "2. conv == 0 (non-convertible)")
    b = b[b["bond_type"].isin(["CDEB", "CMTN"])];       record(b, "3. bond_type in {CDEB,CMTN}")
    b = b[b["ret_eom"].notna()];                        record(b, "4. ret_eom not null")
    b = b[b["amount_outstanding"] > 0];                 record(b, "5. amount_outstanding > 0")

    out = b[KEEP].copy()
    out.to_parquet(C.INTERIM / "bonds_clean.parquet", index=False)
    write_json(C.INTERIM / "bonds_filter_log.json",
               {"generated_utc": utc_now_iso(), "steps": steps})
    log.info("Wrote %s (%s rows)", C.INTERIM / "bonds_clean.parquet", f"{len(out):,}")


if __name__ == "__main__":
    main()
