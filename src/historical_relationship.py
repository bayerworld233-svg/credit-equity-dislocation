"""
Phase 3a — the contemporaneous bond-equity relationship + expanding-window (alpha_t, beta_t).

PRIMARY (approved): pooled OLS  eq_{i,s} = alpha_t + beta_t * bd_{i,s}  over strictly past
months s <= t-1, expanding window, >=24-month minimum history, no firm/month FE, single
common beta. RAW cleaned panel returns (no winsorization in primary).

Outputs:
  data/processed/expanding_betas.parquet   (ym, alpha_t, beta_t, se_beta, n_obs, n_past_months)
  output/tables/monthly_cs_corr.csv
  output/figures/{monthly_cs_corr,expanding_beta,scatter_bd_eq}.png
  output/diagnostics/phase3a_relationship.md
Run: conda run -n credit-equity python -m src.historical_relationship
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
MIN_HISTORY = 24  # months (pre-specified)


def ols(x: np.ndarray, y: np.ndarray):
    """Simple OLS y = a + b x. Returns (a, b, se_b, n)."""
    n = x.size
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    b = ((x - xm) * (y - ym)).sum() / sxx
    a = ym - b * xm
    resid = y - (a + b * x)
    s2 = (resid ** 2).sum() / (n - 2)
    se_b = np.sqrt(s2 / sxx)
    return a, b, se_b, n


def main():
    p = pd.read_parquet(C.PROCESSED / "panel_firm_month.parquet")
    p["t"] = pd.PeriodIndex(p["ym"], freq="M")
    p = p.dropna(subset=["bond_ret_ao", "equity_ret"])
    S = []
    W = lambda *x: S.append(" ".join(str(i) for i in x))
    W(f"# Phase 3a — Contemporaneous bond-equity relationship\n\nGenerated {utc_now_iso()}\n")

    # ---- Contemporaneous diagnostics ----
    overall_corr = p["bond_ret_ao"].corr(p["equity_ret"])
    a_all, b_all, se_all, n_all = ols(p["bond_ret_ao"].values, p["equity_ret"].values)
    W("## 1. Contemporaneous relationship (full panel 2015-01..2025-11)\n")
    W(f"- Pooled corr(bond_ao, equity) = **{overall_corr:.3f}**  (n={n_all:,})")
    W(f"- Pooled OLS: equity = {a_all:.4f} + **{b_all:.3f}**·bond_ao  "
      f"(beta se {se_all:.3f}, t={b_all/se_all:.1f})")

    # monthly cross-sectional correlation
    mcc = p.groupby("t").apply(
        lambda g: g["bond_ret_ao"].corr(g["equity_ret"]) if len(g) > 5 else np.nan,
        include_groups=False).rename("cs_corr").dropna()
    mcc.index = mcc.index.astype(str)
    mcc.to_csv(C.TABLES / "monthly_cs_corr.csv")
    W(f"\n- Monthly cross-sectional corr: mean **{mcc.mean():.3f}**, median {mcc.median():.3f}, "
      f"std {mcc.std():.3f}, min {mcc.min():.3f}, max {mcc.max():.3f}, "
      f"% months positive **{100*(mcc>0).mean():.1f}%**")

    # ---- Expanding (alpha_t, beta_t), strictly past, >=24 months ----
    months = np.array(sorted(p["t"].unique()))
    rows = []
    for t in months:
        past = p[p["t"] < t]
        n_past_months = past["t"].nunique()
        if n_past_months < MIN_HISTORY:
            continue
        a, b, se_b, n = ols(past["bond_ret_ao"].values, past["equity_ret"].values)
        rows.append({"ym": str(t), "alpha_t": a, "beta_t": b, "se_beta": se_b,
                     "n_obs": int(n), "n_past_months": int(n_past_months)})
    betas = pd.DataFrame(rows)
    betas.to_parquet(C.PROCESSED / "expanding_betas.parquet", index=False)

    W("\n## 2. Expanding-window beta_t (strictly past, >=24-month history)\n")
    W(f"- First signal month: **{betas['ym'].min()}**  | last: **{betas['ym'].max()}**  "
      f"({len(betas)} months)")
    W(f"- beta_t: mean **{betas['beta_t'].mean():.3f}**, std {betas['beta_t'].std():.3f}, "
      f"min {betas['beta_t'].min():.3f}, max {betas['beta_t'].max():.3f}; "
      f"first {betas['beta_t'].iloc[0]:.3f} -> last {betas['beta_t'].iloc[-1]:.3f}")
    W(f"- alpha_t: mean {betas['alpha_t'].mean():.4f}, std {betas['alpha_t'].std():.4f}")
    W(f"- All beta_t strictly positive: {'yes' if (betas['beta_t']>0).all() else 'NO'}; "
      f"median beta se {betas['se_beta'].median():.3f} (beta_t/se median "
      f"{(betas['beta_t']/betas['se_beta']).median():.1f})")

    # ---- Figures ----
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(pd.PeriodIndex(mcc.index, freq="M").to_timestamp(), mcc.values, lw=1)
    ax.axhline(mcc.mean(), color="C1", ls="--", lw=1, label=f"mean {mcc.mean():.2f}")
    ax.axhline(0, color="grey", lw=0.6)
    ax.set_title("Monthly cross-sectional corr(bond_ao, equity)"); ax.legend()
    fig.tight_layout(); fig.savefig(C.FIGURES / "monthly_cs_corr.png", dpi=120); plt.close(fig)

    bt = betas.copy(); bt["ts"] = pd.PeriodIndex(bt["ym"], freq="M").to_timestamp()
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(bt["ts"], bt["beta_t"], lw=1.5)
    ax.fill_between(bt["ts"], bt["beta_t"]-2*bt["se_beta"], bt["beta_t"]+2*bt["se_beta"], alpha=.2)
    ax.set_title("Expanding-window beta_t (±2 se)"); fig.tight_layout()
    fig.savefig(C.FIGURES / "expanding_beta.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    m = (p["bond_ret_ao"].abs() < 0.3) & (p["equity_ret"].abs() < 0.6)
    hb = ax.hexbin(p.loc[m, "bond_ret_ao"], p.loc[m, "equity_ret"], gridsize=60, bins="log", cmap="viridis")
    xs = np.linspace(-0.3, 0.3, 50); ax.plot(xs, a_all + b_all*xs, "r-", lw=1.5,
             label=f"OLS beta={b_all:.2f}")
    ax.set_xlabel("bond_ao return"); ax.set_ylabel("equity return")
    ax.set_title("Contemporaneous bond vs equity"); ax.legend()
    fig.colorbar(hb, ax=ax, label="log count"); fig.tight_layout()
    fig.savefig(C.FIGURES / "scatter_bd_eq.png", dpi=120); plt.close(fig)

    (C.DIAGNOSTICS / "phase3a_relationship.md").write_text("\n".join(S) + "\n")
    log.info("Wrote expanding_betas (%d months) + figures + phase3a_relationship.md", len(betas))
    print("\n".join(S))


if __name__ == "__main__":
    main()
