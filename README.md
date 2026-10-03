# Credit–Equity Dislocation
### When a firm's stock and its bonds disagree, which market is right?

A cross-asset quant research study on **same-firm** corporate bonds vs. equities (monthly,
2015–2025, WRDS data). It asks whether information in one market is incorporated into the
other with a delay — and turns the answer into a systematic credit-convergence strategy.

> **Presentation:** open [`report/index.html`](report/index.html) in any browser
> (self-contained, offline). Navigate with **← / →**; press **F** for fullscreen.

---

## The research story (in order)

1. **Original hypothesis — bonds lead equities.** Motivated by cross-market information
   diffusion / investor segmentation, I expected the slower, less-liquid OTC bond market to
   lead the stock when the two diverge.
2. **A stable normal relationship exists.** Same-firm contemporaneous bond/equity correlation
   ≈ 0.42; pooled OLS β ≈ 1.26; an expanding, look-ahead-free β stays in 1.10–1.33 and is
   always positive. This makes a **dislocation** well-defined:
   `Dislocation(i,t) = eq(i,t) − [α̂(t) + β̂(t)·bd(i,t)]`, with α̂, β̂ estimated only on data ≤ t−1.
3. **The data rejected the original hypothesis.** In an unrestricted monthly decomposition,
   **bond → equity is insignificant** (coef ≈ −0.019, t ≈ −0.12), while
   **equity → next-month bond is significant** (coef ≈ +0.030, t ≈ +2.87), conditional on the
   bond's own current return. At the monthly horizon, *equity predicts next-month bond returns;
   the reverse does not.*
4. **It survives falsification.** The equity→bond lead is **not** bond mean-reversion (own-return
   decomposition), **survives Treasury-rate adjustment** (duration×Δy10 and duration-matched
   Treasury-adjusted returns), and **survives stricter month-end price-freshness screens**
   (current TRACE trades only, ≤5-day freshness). It is **~6× larger in high yield** per unit of
   signal — strongest where credit risk dominates.
5. **Strategy — a credit-convergence long/short.** Each month, rank firms by dislocation into
   quintiles; **long Q5** (equity outran credit → bond may catch up), **short Q1**, hold one
   month, rebalance monthly, dollar-neutral. Within a firm, bonds are amount-outstanding-weighted
   into one credit return; **across firms, issuers are equal-weighted**. Returns use
   duration-matched Treasury-adjusted (credit-excess) bond returns to approximate a credit view.
6. **Headline gross backtest** (quintile L/S, equal-weight firms, credit-excess, 2017–2025):

   | Sleeve | Ann. return | Vol | Sharpe | NW t-stat | Hit rate |
   |---|--:|--:|--:|--:|--:|
   | ALL | 5.1% | 4.1% | 1.24 | 2.80 | 72% |
   | High yield | 10.1% | 9.1% | 1.10 | 2.79 | 69% |
   | Investment grade | 2.2% | 1.9% | 1.12 | 2.47 | 76% |

7. **Current example (as-of 2025-11).** Market-wide dislocation dispersion is *below* its history
   (~24th percentile) — this is name-specific, not a market-wide mispricing. **VF Corp** is a
   candidate long-credit dislocation (HY, ~+2.6σ); its catalyst (Dickies sale closed, net debt
   down ~27% ex-leases) is directionally positive for *both* equity and credit, consistent with
   delayed credit repricing rather than a shareholder-vs-creditor event.

### Important framing (please read as such)
- This is a **predictive** relation, **not** proof of causal information flow. Diffusion /
  segmentation is a *hypothesis consistent with* the evidence.
- A **dislocation is a statistical deviation, not automatically a mispricing.**
- Backtest figures are **gross**. Turnover is ~160%/rebalance; single-name cash-bond shorting is
  hard and costly; the cost sensitivity uses **illustrative** assumed basis-point costs, **not**
  measured transaction costs. Full-sample performance is not necessarily regime-invariant (the
  2020 dislocation contributes a visible step, largest in HY).

---

## Data sources & licensing (important)

All security-level inputs come from **licensed WRDS datasets** and are **not** redistributed here:

| Role | WRDS source |
|---|---|
| Corporate bond returns (monthly) | `wrdsapps_bondret.bondret` |
| Equity (CRSP v2 monthly, delisting-adjusted) | `crsp.msf_v2` |
| Bond→equity link (official, point-in-time) | `wrdsapps_link_crsp_bond.bondcrsp_link` |
| Treasury term returns | CRSP Fixed-Term Indices (`crsp.tfz_mth_ft`) |
| Factors | `ff.factors_monthly` |

**This repository contains code, methodology, the presentation, and aggregate results only.**
Raw and derived **row-level WRDS observations** (`data/`, firm-level snapshot CSVs) are
`.gitignore`d and must be regenerated from WRDS by anyone with the appropriate subscription.
Published outputs are aggregate statistics (regression coefficients, portfolio metrics,
distributions, figures). Credentials are never stored in the repo — WRDS auth is read at runtime
only from `~/.pgpass` by the `wrds` package.

### Reproducibility note
Because the underlying data are licensed, the pipeline is **not** runnable end-to-end without a
WRDS account. With access:

```bash
conda create -y -n credit-equity python=3.12 && conda activate credit-equity
pip install -r requirements.txt
python -c "import wrds; db=wrds.Connection(); db.create_pgpass_file(); db.close()"  # one-time auth
conda run -n credit-equity python -m src.extract          # -> data/raw/ (licensed; gitignored)
conda run -n credit-equity python -m src.data_audit
# clean_bonds -> clean_equities -> link_bond_equity -> aggregate_monthly -> panel_audit
# historical_relationship -> dislocation -> predictive_regressions -> own_return_decomposition
# rate_robustness -> freshness_robustness -> backtest_candidateA -> current_snapshot
```

## Repository layout

```
report/index.html      self-contained presentation deck (+ report/assets/ figures)
src/                   extraction, cleaning, linking, panel build, all analyses & backtest
output/figures/        aggregate figures used in the deck
output/tables/         aggregate result tables (firm-level snapshot CSVs are gitignored)
output/diagnostics/    methodology memos & aggregate results (data audit, spec, robustness, backtest)
data/                  WRDS-licensed raw & derived data — gitignored, not distributed
```

*Educational research project. Not investment advice.*
