"""
Phase 2 — attach CRSP permco (issuer) to each clean bond-month via the official
point-in-time WRDS link, with defensive null handling and ambiguity logging.

Rules (approved):
  - Join bond cusip -> bondcrsp_link; keep rows where the bond month-date falls within
    [link_startdt, link_enddt]. Null start -> -inf, null end -> +inf (defensive; none
    exist in the current vintage), and any coalesced rows are counted.
  - Firm key = PERMCO. Drop + log bond-months that map to >1 distinct permco (ambiguous
    issuer); never pick one arbitrarily.

Output: data/interim/bonds_linked.parquet  (bond-month + permco).
Run: conda run -n credit-equity python -m src.link_bond_equity
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso, write_json

log = get_logger()
FAR_PAST = pd.Timestamp("1900-01-01")
FAR_FUT = pd.Timestamp("2262-01-01")


def main() -> None:
    b = pd.read_parquet(C.INTERIM / "bonds_clean.parquet")
    b["date"] = pd.to_datetime(b["date"])
    lk = pd.read_parquet(C.RAW / "bondcrsp_link.parquet")
    for c in ["link_startdt", "link_enddt"]:
        lk[c] = pd.to_datetime(lk[c])

    info = {"generated_utc": utc_now_iso()}
    info["null_link_startdt"] = int(lk["link_startdt"].isna().sum())
    info["null_link_enddt"] = int(lk["link_enddt"].isna().sum())
    # defensive coalesce (no-op given 0 nulls, but explicit)
    lk["ls"] = lk["link_startdt"].fillna(FAR_PAST)
    lk["le"] = lk["link_enddt"].fillna(FAR_FUT)

    n_bm_in = b.drop_duplicates(["cusip", "date"]).shape[0]
    m = b.merge(lk[["cusip", "permno", "permco", "ls", "le"]], on="cusip", how="left")
    matched = m[(m["date"] >= m["ls"]) & (m["date"] <= m["le"])].copy()

    n_bm_linked = matched.drop_duplicates(["cusip", "date"]).shape[0]
    # ambiguous: bond-month -> >1 distinct permco
    npc = matched.groupby(["cusip", "date"])["permco"].transform("nunique")
    ambiguous = matched[npc > 1]
    n_amb = ambiguous.drop_duplicates(["cusip", "date"]).shape[0]
    clean = matched[npc == 1].drop_duplicates(["cusip", "date"]).copy()

    info.update({
        "bond_months_in": int(n_bm_in),
        "bond_months_linked": int(n_bm_linked),
        "bond_months_unlinked": int(n_bm_in - n_bm_linked),
        "ambiguous_multi_permco_bond_months_dropped": int(n_amb),
        "bond_months_out": int(len(clean)),
        "n_permco_out": int(clean["permco"].nunique()),
    })
    log.info("bond-months in=%s linked=%s (unlinked=%s) ambiguous-dropped=%s out=%s permco=%s",
             f"{n_bm_in:,}", f"{n_bm_linked:,}", f"{n_bm_in-n_bm_linked:,}",
             f"{n_amb:,}", f"{len(clean):,}", f"{clean['permco'].nunique():,}")

    clean = clean.drop(columns=["ls", "le"])
    clean.to_parquet(C.INTERIM / "bonds_linked.parquet", index=False)
    write_json(C.INTERIM / "link_log.json", info)
    log.info("Wrote %s", C.INTERIM / "bonds_linked.parquet")


if __name__ == "__main__":
    main()
