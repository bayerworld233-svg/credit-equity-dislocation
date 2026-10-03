# Phase 3 Specification Memo — historical relationship, dislocation, predictive test

Prepared 2026-10-02. Proposes ONE simple primary specification. No estimation, no
backtests, no parameter search. Robustness alternatives listed separately at the end.

Notation: firm = permco `i`; month = `t`; `eq_{i,t}` = `equity_ret`; `bd_{i,t}` =
`bond_ret_ao` (AO-weighted fresh bond return). Panel = `data/processed/panel_firm_month.parquet`.

---

## 1. Structure of the historical relationship — POOLED, single β (not firm-specific)

**Primary:** one pooled linear relationship with a single intercept and slope, estimated on
an **expanding window of strictly past data**:
> `eq_{i,s} = α + β·bd_{i,s} + e_{i,s}` for all firm-months with `s ≤ t−1`.

Re-estimated each month `t` as the window grows → `(α̂_t, β̂_t)`.

**Why pooled, not firm-specific:**
- *Statistical:* a firm-by-firm time-series β on monthly data is very noisy — many firms have
  short/gappy histories (median ~ dozens of months), so firm-level β would have large standard
  errors and produce unstable residuals that contaminate the signal. Pooling borrows strength
  across ~750 firms/month and identifies β precisely.
- *Economic:* the average equity–bond return sensitivity is a sound first-order structural
  link (contemporaneous corr = 0.42 in the panel). Cross-firm heterogeneity in that
  sensitivity (leverage, rating) is a *refinement*, not the baseline.
- *Simplicity first* (project rule): start with the simplest defensible structure.

## 2. Firm and/or month effects in the relationship — NONE in the baseline

**Primary:** no firm fixed effects and no month fixed effects — a single pooled `(α, β)`.
- *Month FE* would be equivalent to demeaning each month (a Fama-MacBeth-style cross-sectional
  relationship); it removes the common market-wide bond/equity comovement and redefines the
  dislocation as *relative to peers that month*. Reasonable, but a different object — kept as
  the leading **robustness** variant.
- *Firm FE* would absorb each firm's average return, turning the residual into a within-firm
  deviation. This risks baking a persistent firm component into the signal; excluding FE keeps
  the residual transparent. Firm FE is a **robustness** variant.
- Known caveat (to test in robustness, not baseline): without firm FE the residual can carry a
  persistent firm component; we address it downstream via a momentum/past-return control and
  the month-demeaned variant — not by complicating the baseline.

## 3. Expanding-window minimum-history requirement — 24 months

**Primary:** require **≥ 24 months** of pooled history (`s ≤ t−1`) before producing a signal
at `t`. With ~800 firms/month this is ~19,000 observations for 2 parameters — amply
identified — while spanning two years of varied conditions. Chosen a priori (a conventional
2-year minimum), **not** tuned. (12-month and 36-month = robustness.)

## 4. Dislocation — exact definition and sign convention

> **`Dislocation_{i,t} = eq_{i,t} − (α̂_t + β̂_t · bd_{i,t})`**

i.e. the firm's realized month-`t` equity return minus the equity return implied by its
month-`t` bond return under the past-estimated relationship. It is the **out-of-sample
residual** (parameters from `≤ t−1`, applied to month-`t` returns).

**Sign convention:**
- `Dislocation > 0`: equity outperformed what its bonds imply → **equity relatively rich /
  bonds relatively cheap** (equity ran ahead, or bonds sold off without equity following).
- `Dislocation < 0`: equity underperformed what its bonds imply → **equity relatively cheap /
  bonds relatively rich** (equity fell more than bonds, or bonds rallied without equity).

It is a *dislocation*, not asserted mispricing, unless the predictive evidence supports it.

## 5. First valid signal month

Sample starts 2015-01. With a 24-month strictly-past window, the first estimable month is
`t−1 = 2016-12` (window 2015-01..2016-12), so the **first signal month is `t = 2017-01`**,
first predictive pair = `Dislocation_{2017-01}` → `eq_{2017-02}`. Last signal month
`t = 2025-11` (bond window end) → predicts `eq_{2025-12}` (available). **Predictive sample:
t = 2017-01 … 2025-11 (107 signal months).**

## 6. Information set at month t — no look-ahead (demonstration)

At the **end of month `t`** (signal time) the signal uses only:
- `(α̂_t, β̂_t)` estimated on firm-months with `s ≤ t−1` (strictly past);
- `bd_{i,t}` and `eq_{i,t}` (realized, known at end of `t`).
Therefore `Dislocation_{i,t}` depends only on information available by end of `t`. The target
`eq_{i,t+1}` is realized at end of `t+1` and **never** enters `α̂_t`, `β̂_t`, or
`Dislocation_{i,t}`. (Panel integrity already verified: forward column equals the next month's
return with 0 mismatches; share-class weights use prior-month cap.)
*Scope note:* the predictive regression below is an in-sample hypothesis test (full-period γ);
the signal is strictly no-look-ahead. A real-time tradable backtest (later phase) will form
positions using only past information.

## 7. Primary predictive regression (one-month horizon)

> **`eq_{i,t+1} = a + γ · Dislocation_{i,t} + ε_{i,t+1}`**

- Pooled OLS over all valid signal firm-months (t = 2017-01..2025-11).
- **Standard errors: two-way clustered by firm (permco) and month** (cross-sectional and
  serial dependence both present).
- Report `γ`, two-way-clustered t-stat, R², N.
- **Convergence hypothesis: `γ < 0`** (equity reverts toward the bond-implied level) — tested,
  not assumed; `γ > 0` (continuation) and `γ ≈ 0` are admissible outcomes.

**Reverse direction (co-primary, to establish lead/lag asymmetry):** identical signal, bond
target —
> **`bd_{i,t+1} = a + δ · Dislocation_{i,t} + ε_{i,t+1}`**
If bonds lead equities: `γ < 0`, `δ ≈ 0`. If equities lead bonds: bonds catch up (`δ`
significant) while `γ ≈ 0`. This decides A/B/C/D from the brief empirically.

**Outlier handling (locked policy, applied here):** winsorize the *signal-construction return
inputs* (`bd`, `eq` used for β and the residual) and the `Dislocation` regressor
cross-sectionally at **1%/99% each month**; leave the **forward dependent returns**
(`eq_{t+1}`, `bd_{t+1}`) **un-winsorized**.

---

## Primary specification (for approval)
1. Relationship: pooled OLS `eq = α + β·bd`, **expanding window ≤ t−1**, **≥24-month** min
   history, **no firm/month FE**, single `(α̂_t, β̂_t)`.
2. `Dislocation_{i,t} = eq_{i,t} − (α̂_t + β̂_t·bd_{i,t})` (equity minus bond-implied).
3. First signal 2017-01; predictive sample 2017-01..2025-11.
4. Primary test `eq_{t+1} = a + γ·Dislocation_t + ε`, two-way clustered SE; `γ<0` = convergence.
5. Reverse test `bd_{t+1} = a + δ·Dislocation_t + ε`.
6. Winsorize RHS/inputs 1/99 monthly; forward returns raw.

## Robustness alternatives (later; NOT chosen by performance)
- Relationship: month-demeaned (cross-sectional / Fama-MacBeth-style) β; firm FE; rolling
  60-month window; separate β for IG vs HY.
- Signal: cross-sectionally standardized (z-scored) dislocation; through-`t` (in-sample) window.
- Min history: 12 and 36 months.
- Inference: Fama-MacBeth with Newey-West; month-FE panel.
- Controls (only after the simple effect is established): past equity return
  (momentum/reversal), size (log firm_mktcap), industry (SIC), rating (`frac_ig_ao`),
  duration/Treasury (rate-exposure test), IG/HY split.
- Dependent variable: excess (−rf) and factor-adjusted returns (for portfolio-alpha stage).
- Horizons: cumulative 2- and 3–4-month (only after the t+1 result; no horizon mining).

**STOP for approval before estimating.**
