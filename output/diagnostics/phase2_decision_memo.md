# Phase 2 Decision Memo — Credit–Equity Dislocation

Prepared 2026-10-02. No regressions/backtests run. Each decision separates
**[DOC]** documented data definitions, **[FACT]** empirical facts from our extract,
and **[REC]** interpretation/recommendation.

Sources for [DOC]: WRDS Postgres column comments (`pg_description`) on
`wrdsapps_bondret.bondret`, and the official `fisd.fisd_code` lookup (`type='BOND_TYPE'`).

---

## Decision 1 — Bond universe

**[DOC] Bond-type codes (`fisd.fisd_code`, authoritative):**
- `CDEB` = "US Corporate Debentures"
- `CMTN` = "US Corporate MTN" (medium-term note)
- `CMTZ` = "US Corporate MTN Zero" (zero-coupon MTN)
- `CP` = "US Corporate Paper" (commercial paper)
- The WRDS Bond Returns file contains only these four corporate straight-debt types
  (ABS, MBS, munis, Treasuries, convertibles-as-type, preferreds are *separate* codes,
  not present in our extract).

**[DOC] `price_eom_flg` (column comment):** "Flag to indicate if EOM price is current
or carried forward from previous months." → `Current` = an actual end-of-month price;
`CryFwd` = price carried forward because the bond did not trade near month-end (stale).

**[FACT]**
- CMTZ = 55.9% of rows, 73% carried-forward, 78% zero-return. CDEB = 35.4%, 5.3% stale,
  0.09% zero. CMTN = 8.7%, 39% stale.
- Fresh-price rate within CDEB+CMTN: IG 89.3% vs HY 81.1% (stale pool is 25% HY vs 15%
  HY in the fresh pool).
- Monthly fresh-price rate is stable (mean 88.2%, min 84.1% in 2023-02) and was 89.8%
  in the 2020-03 COVID stress month — trading did **not** dry up in the crash.
- Convertibles within CDEB+CMTN: 7,477 bond-months (0.5%), flaggable via `conv`.
- Firm cross-section is nearly unchanged by the restriction: 878 firms/mo (raw) →
  849 (Current+CDEB) → ~867 (CDEB only).

**[REC]** Primary universe = **`bond_type ∈ {CDEB, CMTN}`, `conv=0`, `price_eom_flg='Current'`**.
This is *economically* justified, not just "cleaner data":
1. CDEB/CMTN are plain-vanilla senior corporate credit — the cleanest read on firm credit.
2. **CMTZ zero MTNs** are largely illiquid retail/structured notes whose returns are 78%
   stale zeros → they carry almost no fresh information and would inject mechanical zeros.
3. **Convertibles** are equity-linked by construction and would mechanically correlate
   with equity, contaminating the bond→equity test — excluding them is required, not optional.
4. `Current`-only is necessary because a carried-forward price produces a spurious 0 return.

**Selection bias this introduces (must be disclosed and tested):**
- *Liquidity selection*: we keep bonds that traded near month-end; HY/distressed bonds are
  modestly less likely to be fresh (81% vs 89%). Risk: if a firm's bonds stop trading
  exactly as credit deteriorates, we could miss the most informative distress signals.
  Evidence mitigates but does not eliminate this: fresh-rate held up in 2020-03.
- *Firm-type external validity*: results generalize to larger, bond-issuing public firms,
  not small caps — inherent to the same-firm research question.
- Robustness: re-run including CMTZ and including CryFwd (raw) to bound the selection effect.

---

## Decision 2 — Firm-level bond aggregation

**[DOC]** `amount_outstanding` = "The amount of the issue remaining outstanding"
(units not stated in the comment; **inferred** $thousands from magnitudes vs `offering_amt`).
`ret_eom` = "Return-End of Month" (decimal).

**[FACT]** On the primary universe (fresh CDEB+CMTN, linked): 112,334 firm-months,
78.7% with ≥2 bonds. `amount_outstanding` missing 0.01%, ≤0 only 0.014%.
- Cross-method correlation (firm-months with ≥2 bonds): AO vs EW 0.982, AO vs median
  0.982, EW vs median 0.979.
- Typical disagreement small: |AO−EW| median 9.4bp (p95 83bp); |AO−median| median 17bp
  (p95 112bp). Within-firm bond-return dispersion: median 104bp std (p95 376bp).
- Largest single bond's AO weight: median 25%, p95 63%.

**[REC]** Primary = **amount-outstanding-weighted mean** of fresh-priced bond returns.
Rationale (economic + data quality): it is the value-weighted credit signal — it weights
each issue by the size of the actual claim, matching how the firm's aggregate debt is
priced; `amount_outstanding` coverage is essentially complete; and the largest bond is
usually the most liquid/most informative. The three methods agree to ρ≈0.98, so this is a
low-stakes choice. **Robustness:** median (robust to a single corrupt bond print) and
equal-weight. Chosen on reasoning above, **not** on predictive performance.

---

## Decision 3 — Outlier treatment (pre-specified, performance-blind)

**[FACT] Tails.**
- Bond `ret_eom`, primary universe (fresh CDEB+CMTN): p0.1 −26.5%, p1 −8.7%, p99 +9.3%,
  p99.9 +23.8%; |ret|>100% only 41 obs (0.004%).
- Equity `mthret` (all): p1 −40.9%, p99 +50.7%, p99.9 +155.9%; |mthret|>100% 2,723
  (0.25%), >200% 682 (0.062%) — fatter tails (distress/microcaps/delisting).

**[REC] Two separate mechanisms, pre-specified now:**
1. *Data-validity screens (drop; these are errors, not outliers):* `amount_outstanding`≤0;
   `duration`∉(0,40]; corrupt `yield` is avoided by **not using the yield field** (22.7%
   negative). Document counts; never silent.
2. *Outlier winsorization:* cross-sectional, **by month**, at **1% / 99%**, applied to
   right-hand-side variables only (the firm bond signal / dislocation and controls).
   **Realized equity returns used as the regression dependent variable and for portfolio
   P&L are left un-winsorized** (winsorizing realized returns would misstate tradable
   performance). Robustness: 0.5/99.5, and no-winsorization; trimming instead of winsorizing.
Thresholds are fixed a priori and will not be tuned to results.

---

## Decision 4 — Is the signal just a Treasury-rate/duration effect?

**[DOC]** `duration` = "Duration" (years; 99.9% plausible in (0,40]). `tmt` = "Time to
Maturity (Years)". Raw bond return = credit component + rate/duration component.

**[REC] Simple, interview-appropriate, layered:**
- *Primary diagnostic (no extra data):* add the firm's AO-weighted **duration** and a
  **duration × aggregate-Treasury-return** term as controls in the predictive regression.
  If the dislocation coefficient is essentially unchanged, the signal is not a rates artifact.
  Also report results **within duration terciles** and **separately for IG vs HY**.
- *Robustness (one extra series):* build a **duration-matched credit-excess bond return**
  = `ret_eom` − (duration-matched Treasury return), rebuild the signal on it, and confirm
  the result survives. Treasury returns by maturity from CRSP Treasury fixed-term indices
  (`crsp_a_treasuries`/`crsp_q_treasuries` — **exact table to verify at implementation**);
  FRED constant-maturity yields are a fallback.
- Logic: a common rate shock moves all bonds proportionally to duration; because the
  signal is **cross-sectional** (within-month ranking), controlling for duration / sorting
  within duration isolates the credit-specific component.

---

## Decision 5 — Minimum coverage per firm-month

**[FACT]** 78.7% of firm-months have ≥2 fresh bonds; requiring ≥2 drops ~21% of
firm-months. A single bond is a noisy firm-credit proxy (within-firm dispersion median
~104bp). Multi-bond firms skew larger (more issues), so a ≥2 rule adds a size/liquidity tilt.

**[REC]** Primary = **≥1 fresh-priced bond** (aggregating over fresh-priced bonds only).
This is the minimum necessary (removes pure-stale firms) while preserving breadth and
avoiding a selection tilt toward large multi-issue firms. ≥1 is *sufficient as the
baseline*, but single-bond firm-months are noisier, so: **Robustness** = require ≥2 fresh
bonds (and, as a further check, require fresh bonds to cover a minimum share of the firm's
outstanding). Report the single-bond subset separately.

---

## Proposed specifications (for approval)

**PRIMARY**
- Bonds: `bond_type ∈ {CDEB, CMTN}`, `conv=0`, `price_eom_flg='Current'`, valid
  (`amount_outstanding>0`, `duration∈(0,40]`), linked to CRSP common equity via the
  official point-in-time link.
- Equity: CRSP v2 common equity (`securitytype='EQTY'`, `sharetype='NS'`,
  `issuertype ∈ {CORP, REIT}`), delisting-adjusted `mthret`.
- Firm-month bond signal: AO-weighted mean of fresh bond `ret_eom`; **≥1** fresh bond.
- Outliers: monthly 1/99 winsorization of RHS only; realized returns un-winsorized.
- Window: 2015-01→2025-11 signal; equity to 2025-12 for t+1. No look-ahead (expanding
  estimation; point-in-time link).

**ROBUSTNESS**
- Universe: + CMTZ; + CryFwd (raw); CDEB-only.
- Aggregation: median; equal-weight.
- Coverage: ≥2 fresh bonds; fresh-AO-coverage threshold.
- Outliers: 0.5/99.5; none; trimming.
- Rates: duration + duration×Treasury controls; duration-matched credit-excess signal;
  within-duration and IG/HY splits.
- Inference: Fama-MacBeth; double-clustered (firm & month) SEs.

**STOP for approval before implementing Phase 2.**

---

# Addendum (2026-10-02) — resolved items before locking the universe

## A. CMTZ inclusion — is there an *independent* reason to exclude (beyond staleness)?

**[DOC]** `fisd.fisd_code`: `CMTZ` = "US Corporate MTN Zero". The name alone does **not**
establish "structured note" — tested descriptively below. Comparison is Current-priced,
`conv=0`:
- **A** = CDEB + CMTN
- **B** = CDEB + CMTN + CMTZ

**[FACT]**
| metric | A (CDEB+CMTN) | CMTZ (the increment) |
|---|---|---|
| bond-months | 1,220,534 | 473,798 |
| unique issuers (`company_symbol`) | — | **46** |
| **incremental linked firms (permco)** | 1,439 | **+1** |
| linked firms/month | 856 | 857 (B) |
| IG / HY | 85.4% / 14.6% | **5.3% / 94.7%** |
| amount_outstanding, median | **$500M** | **$3.1M** (p95 $30M) |
| offering_amt, median | $500M | $3.2M |
| time to maturity, median | 6.3 yr | 2.0 yr |
| duration, median | 5.3 yr | 2.1 yr |
| coupon, median | 4.375% | **0** (all) |
| ret_eom p5 / med / p95 | −4.1% / +0.3% / +4.6% | −11.6% / +2.0% / +21.0% |

**[REC] Exclude Current-priced, non-convertible CMTZ from the primary universe — now on
evidence, not the instrument name.** Independent reasons, each sufficient:
1. **No incremental breadth.** CMTZ adds 473,798 bond-months but only **+1 firm** — the 46
   issuers are already present via their CDEB/CMTN. For a firm-level cross-sectional study
   they are redundant.
2. **Extreme issuer concentration.** 124,173 tiny bonds across **46 issuers** (bank/dealer
   shelf programs). Under any firm aggregation they would swamp those ~46 firms' signals
   with thousands of micro zero-coupon notes instead of their benchmark senior debt.
3. **Non-comparable instrument.** Median issue **$3.1M** (≈160× smaller), zero-coupon,
   short-dated, 95% HY-classified, far wider return dispersion (partly accretion/structure,
   not clean credit repricing). This is the structured/retail-note profile — now documented.

Kept as a **robustness** universe (+CMTZ) so the exclusion is transparent and bounded.

## B. Link-date semantics & null handling

**[DOC]** `bondcrsp_link` column comments are plain labels ("Link Start/End Date", etc.);
table "Bond CRSP Link (Updated 2026-09-04)".
**[FACT]** **Zero nulls** in all six date fields (link/crsp/trace start & end, n=383,120).
No far-future open-ended sentinel; active links are right-censored at the update date
(`link_enddt` max = 2025-12-31; 34,097 rows end exactly there).
**[REC]** The Phase-1 point-in-time filter `link_startdt ≤ date ≤ link_enddt` is correct and
drops nothing erroneously (there are no open-ended rows). Phase-2 link code will still
**defensively coalesce** a null `link_startdt`→−∞ and null `link_enddt`→+∞ in case a future
WRDS refresh introduces them, and will log any such rows rather than dropping silently.

## C. Multiple PERMNO per bond-month & PERMCO↔PERMNO rule

**[DOC]** `bondcrsp_link` provides both `permno` and `permco` per bond. CRSP `permco` =
issuer/company; `permno` = security (share class). CRSP exposes `securityhdrflg` (Y/N) =
"Security Header Flag".
**[FACT]** On the primary universe: 1,014,541 linked bond-months; **1,568 (0.155%) map to
>1 permno at once — and 100% of those are *different* permco** (not share classes), i.e.
genuinely ambiguous issuer assignment (e.g., M&A/parent–subsidiary overlap). Separately,
within linked firms only **1.9% of permco-months** have >1 common-equity permno; **3.4% of
firms (42/1,253)** ever have multiple common share classes.
**[REC] Documented rule — never "first permno":**
1. **Firm key = PERMCO** (issuer). The bond signal and equity are both assembled at permco
   level. Bonds join to permco via the point-in-time link.
2. **Ambiguous bonds (bond-month → >1 permco):** drop these 0.155% of bond-months
   explicitly and log the count. Do not arbitrarily pick an issuer.
3. **Share classes (permco → >1 common-equity permno):** compute the firm-month equity
   return as the **market-cap-weighted average across the permco's common-equity permnos**
   (`securitytype='EQTY'`, `sharetype='NS'`, `issuertype∈{CORP,REIT}`), using prior-month
   `mthcap` as weights (no look-ahead). Robustness: use the single largest-cap permno.
   (Most firms have one; this only affects ~3.4%.)

## D. Should `duration` be an eligibility filter? — No.

**[DOC]** `bondret.duration` column comment is literally **"Duration"** — WRDS documents
**no units and no method** (Macaulay vs modified). Empirically consistent with *years*
(primary-universe median 5.34, p99 18.3, 99.9% within (0,40]), but the field alone cannot
confirm the convention. Stated as inferred, per project rule.

**[FACT]** Primary universe without any duration screen = **994,307 bond-months /
111,683 firm-months**. Candidate duration screens would remove: missing **5,879
(0.591%)**, ≤0 **0**, >40 **6 (0.001%)**, `duration>tmt` **1,181 (0.119%)** — **all of
which have a valid `ret_eom`**. Firm-months lost entirely: **91 (0.08%)**. `ret_eom` is
computed from end-of-month prices and does **not** depend on `duration`.

**[REC] Remove duration from primary eligibility.** The two uses must be separated:
1. *Rate/duration adjustment (legitimate):* duration is an input to the **robustness**
   test for Treasury-rate exposure only.
2. *Eligibility filter for the raw return (not justified):* gating the return sample on an
   **ancillary** field would discard valid returns and introduce selection toward bonds
   with well-defined duration (tilting away from complex/odd structures) for no benefit to
   the primary signal.
Therefore the primary bond sample requires only the inputs the signal/aggregation actually
use. In the rate-exposure robustness, validate duration *there* with the principled rule
**`0 < duration ≤ tmt`** (duration cannot exceed time-to-maturity — a logical constraint,
not an arbitrary cutoff; the old "40" is unnecessary and dropped), handling missing
duration by excluding only from that specific test.

## Final locked-pending-approval primary universe

- **Bonds:** `price_eom_flg='Current'`, `conv=0`, `bond_type ∈ {CDEB, CMTN}` (CMTZ/CP
  excluded), **valid `ret_eom`** and **`amount_outstanding>0`** (the latter is required
  because AO is the aggregation weight — intrinsic to construction, unlike duration).
  **No duration screen.** `yield` field unused.
- **Link:** official point-in-time `bondcrsp_link`, bond→**permco**; drop bond-months
  mapping to >1 permco (logged).
- **Equity:** CRSP v2 common equity (`EQTY`/`NS`/`CORP|REIT`), delisting-adjusted `mthret`;
  firm-month return = prior-cap-weighted across the permco's common permnos.
- **Firm bond signal:** AO-weighted mean of the firm's fresh CDEB/CMTN `ret_eom`; **≥1**
  fresh bond required. (For EW/median robustness, AO validity is not required.)
- **Outliers:** monthly 1/99 winsorization of RHS variables only; realized returns
  un-winsorized; validity screens applied and logged.
- **Duration:** used only in the rate-exposure robustness, validated there by
  `0 < duration ≤ tmt`.
- **Window:** signal 2015-01→2025-11; equity to 2025-12 for t+1.
