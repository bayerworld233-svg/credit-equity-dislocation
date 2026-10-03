"""
Central configuration: paths, sample window, WRDS table references, and a
secure WRDS connection helper.

Credential policy (NEVER violated):
  - The WRDS password is read ONLY from ~/.pgpass by the `wrds` package itself.
  - This module never reads, prints, logs, or stores the password.
  - The WRDS *username* (not secret) is resolved from the WRDS_USERNAME env var,
    or, failing that, from field 4 of the matching ~/.pgpass line.
"""
from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (anchored to the repo root = parent of this file's directory)
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUTPUT = ROOT / "output"
DIAGNOSTICS = OUTPUT / "diagnostics"
FIGURES = OUTPUT / "figures"
TABLES = OUTPUT / "tables"

for _p in (RAW, INTERIM, PROCESSED, DIAGNOSTICS, FIGURES, TABLES):
    _p.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# Sample window (LOCKED decisions — see CLAUDE.md)
# ----------------------------------------------------------------------------
# Bond signal / dislocation window. 2025-11 is the last fully-complete bond month.
BOND_START = "2015-01-01"
BOND_END = "2025-11-30"
# Equity window extends one month past the bond window so the last signal month
# (2025-11) has an available t+1 forward equity return (2025-12). CRSP ends 2025-12-31.
EQUITY_START = "2015-01-01"
EQUITY_END = "2025-12-31"

# ----------------------------------------------------------------------------
# WRDS table references (verified in Phase 0 — do not change without re-inspecting)
# ----------------------------------------------------------------------------
TBL_BONDRET = "wrdsapps_bondret.bondret"
TBL_BONDCRSP_LINK = "wrdsapps_link_crsp_bond.bondcrsp_link"
TBL_EQUITY = "crsp.msf_v2"
TBL_FF = "ff.factors_monthly"

WRDS_PGHOST = "wrds-pgdata.wharton.upenn.edu"


def resolve_wrds_username() -> str:
    """Resolve the (non-secret) WRDS username without touching the password.

    Priority: WRDS_USERNAME env var -> field 4 of the matching ~/.pgpass line.
    """
    env = os.environ.get("WRDS_USERNAME")
    if env:
        return env.strip()

    pgpass = Path.home() / ".pgpass"
    if pgpass.exists():
        for line in pgpass.read_text().splitlines():
            if line.startswith("#") or not line.strip():
                continue
            # format: hostname:port:database:username:password
            parts = line.split(":")
            if len(parts) >= 5 and WRDS_PGHOST in parts[0]:
                return parts[3].strip()
    raise RuntimeError(
        "Could not resolve WRDS username. Set WRDS_USERNAME env var or ensure "
        "~/.pgpass contains a WRDS line (hostname:port:db:username:password)."
    )


def get_connection():
    """Return an authenticated wrds.Connection. Password is handled by ~/.pgpass."""
    import wrds

    return wrds.Connection(wrds_username=resolve_wrds_username())
