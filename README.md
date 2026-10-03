# Credit–Equity Dislocation
### When a firm's stock and its bonds disagree, which market is right?

**▶ View the presentation → https://bayerworld233-svg.github.io/credit-equity-dislocation/**
(opens the slide deck directly in the browser — ← / → to navigate, **F** for fullscreen)

A cross-asset quant research study on **same-firm** corporate bonds vs. equities (monthly,
2015–2025, WRDS data). It asks whether information in one market is incorporated into the other
with a delay — and turns the answer into a systematic credit-convergence strategy.

---

## Research question
Same-firm stocks and corporate bonds are claims on one enterprise value but trade in segmented
markets. When they diverge from their historical relationship, **which market — if either —
predicts the other's convergence?** (Original hypothesis: bonds lead equities.)

## Data (licensed — not redistributed)
WRDS **Bond Returns** (TRACE-based) + **CRSP** equities, joined on the official bond–CRSP
**point-in-time** link; Treasury term returns and Fama–French factors. Panel: **98,373
firm-months / 1,244 firms**, 2015-01→2025-11 (signal/backtest 2017-01→2025-11). Security-level
WRDS data are **not** included here (see *Licensing* below).

## Signal construction (no look-ahead)
Estimate the normal relationship on **past data only** (`s ≤ t−1`):
`R^Equity_{i,s} = α_t + β_t R^Bond_{i,s}`, then score month t:
**Dislocation** `D_{i,t} = R^Equity_{i,t} − (α̂_t + β̂_t R^Bond_{i,t})` — the residual from the
historical benchmark (a statistical deviation, not automatically a mispricing).

## Main empirical finding
The original "bonds lead equities" hypothesis is **rejected**. Instead, current **equity** return
carries incremental predictive information for **next-month same-firm corporate-bond** return,
after controlling for the bond's own current return:
`R^Bond_{i,t+1} = λ_t + β₁ R^Bond_{i,t} + β₂ R^Equity_{i,t} + ε`, with **β₂ ≈ +0.030, t ≈ 2.87**
(month FE, firm & month clustered SEs). This is a **predictive** relation, not proof of causal
information flow.

## Trading interpretation
A monthly cross-sectional credit-convergence long/short: rank firms by dislocation,
**long Q5** (equity outran credit → bond expected to catch up) / **short Q1**, dollar-neutral,
1-month hold, duration-matched Treasury-adjusted (credit-excess) bond returns. Gross backtest:
ALL ≈ 5.1%/yr (Sharpe 1.24, NW-t 2.80); **HY ≈ 10.1%/yr**. Results are **gross** — turnover
≈160%/rebalance and single-name cash-bond shorting/HY liquidity make net tradability the open
question. VF Corp (Nov-2025) is a current *candidate*, pending an event check (dislocation ≠ mispricing).

## Key robustness (equity coefficient β₂)
| Specification | β₂ | t |
|---|--:|--:|
| Baseline decomposition | +0.030 | 2.87 |
| Treasury / duration adjusted | +0.030 | 2.96 |
| ≤5-day fresh bond prices | +0.029 | 2.70 |
| High yield vs IG | ≈ 6× larger in HY | |

Survives own-return decomposition, Treasury/duration adjustment, and stricter month-end
price-freshness; economically much larger in HY. "Survives" reduces the plausibility of these
alternatives — it does not fully disprove them.

## Repository structure
```
docs/            published presentation (GitHub Pages) — index.html + assets/
report/          authoring copy of the deck
src/             full pipeline: extract → clean → link → panel → analyses → backtest → snapshot
output/figures/  aggregate figures
output/tables/   aggregate result tables
output/diagnostics/  methodology memos & aggregate results
data/            WRDS-licensed raw & derived data — gitignored, not distributed
```

## Reproduction
Licensed data are not distributed, so the pipeline is not runnable end-to-end without a WRDS
account. With access:
```bash
conda create -y -n credit-equity python=3.12 && conda activate credit-equity
pip install -r requirements.txt
python -c "import wrds; db=wrds.Connection(); db.create_pgpass_file(); db.close()"   # one-time auth
conda run -n credit-equity python -m src.extract        # -> data/raw/ (licensed; gitignored)
# clean_bonds → clean_equities → link_bond_equity → aggregate_monthly → panel_audit
# historical_relationship → dislocation → predictive_regressions → own_return_decomposition
# rate_robustness → freshness_robustness → backtest_candidateA → current_snapshot
```

## Licensing
Security-level inputs come from **licensed WRDS datasets** and are **not** redistributed.
Published outputs are aggregate statistics, code, methodology, and the presentation. WRDS auth is
read at runtime only from `~/.pgpass` — no credentials are stored in the repo.

*Educational research project. Not investment advice.*
