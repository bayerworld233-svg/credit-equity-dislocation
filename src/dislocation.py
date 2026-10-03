"""
Phase 3b — bond-implied equity return and the month-t dislocation signal.

For each firm-month t with an expanding estimate (t >= first signal month):
  eq_hat_{i,t} = alpha_t + beta_t * bd_{i,t}
  Dislocation_{i,t} = eq_{i,t} - eq_hat_{i,t}
Positive => equity outperformed its bond-implied same-month return; negative => underperformed.
Dislocation is kept CONTINUOUS (no thresholding/filtering on magnitude). RAW returns.

Output: data/processed/signal_panel.parquet  (+ dislocation diagnostics & figure).
Run: conda run -n credit-equity python -m src.dislocation
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from .utils import get_logger, utc_now_iso

log = get_logger()


def main():
    p = pd.read_parquet(C.PROCESSED / "panel_firm_month.parquet")
    betas = pd.read_parquet(C.PROCESSED / "expanding_betas.parquet")

    sig = p.merge(betas[["ym", "alpha_t", "beta_t"]], on="ym", how="inner")
    sig = sig.dropna(subset=["bond_ret_ao", "equity_ret"])
    sig["eq_implied"] = sig["alpha_t"] + sig["beta_t"] * sig["bond_ret_ao"]
    sig["dislocation"] = sig["equity_ret"] - sig["eq_implied"]

    cols = ["permco", "ym", "yyyymm", "date", "n_bonds", "firm_mktcap", "siccd",
            "frac_ig_ao", "bond_ret_ao", "equity_ret", "eq_implied", "dislocation",
            "equity_ret_fwd1", "bond_ret_ao_fwd1"]
    sig = sig[cols].sort_values(["ym", "permco"]).reset_index(drop=True)
    sig.to_parquet(C.PROCESSED / "signal_panel.parquet", index=False)

    S = []; W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 3b — Dislocation signal\n\nGenerated {utc_now_iso()}\n")
    W(f"- Signal firm-months: **{len(sig):,}**, firms **{sig['permco'].nunique():,}**, "
      f"months **{sig['ym'].min()}..{sig['ym'].max()}** ({sig['ym'].nunique()})")
    d = sig["dislocation"]
    W(f"- Dislocation (continuous, raw): mean {d.mean():.5f}, median {d.median():.5f}, "
      f"std {d.std():.4f}")
    W("  quantiles: " + ", ".join(f"p{int(q*100)}={d.quantile(q):.4f}"
      for q in [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]))
    W(f"- min {d.min():.4f}, max {d.max():.4f}; "
      f"with valid eq_fwd1: {int(sig['equity_ret_fwd1'].notna().sum()):,}")
    # by year
    sig["yr"] = sig["ym"].str[:4]
    by = sig.groupby("yr")["dislocation"].agg(["mean", "std", "count"]).round(5)
    by.to_csv(C.TABLES / "dislocation_by_year.csv")
    W("\n**Dislocation by year (mean ~0 by construction; std = dispersion):**\n")
    W(by.to_markdown())

    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.hist(d[d.abs() < 0.4], bins=120, color="C0")
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_title("Dislocation distribution (|d|<0.4)"); ax.set_xlabel("dislocation")
    fig.tight_layout(); fig.savefig(C.FIGURES / "dislocation_hist.png", dpi=120); plt.close(fig)

    (C.DIAGNOSTICS / "phase3b_dislocation.md").write_text("\n".join(S) + "\n")
    log.info("Wrote signal_panel (%s rows) + dislocation diagnostics", f"{len(sig):,}")
    print("\n".join(S))


if __name__ == "__main__":
    main()
