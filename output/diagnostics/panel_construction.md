# Phase 2 Panel Construction Diagnostics

Generated: 2026-10-03T00:39:37Z

## 1. Filtering, linking & drop counts (each step)

**Bond cleaning:**

| step                              |   n_rows |   n_bonds |   n_bond_months |
|:----------------------------------|---------:|----------:|----------------:|
| 0. raw bondret (2015-01..2025-11) |  3153572 |    160526 |         3153572 |
| 1. price_eom_flg='Current'        |  1698635 |    160523 |         1698635 |
| 2. conv == 0 (non-convertible)    |  1694335 |    158402 |         1694335 |
| 3. bond_type in {CDEB,CMTN}       |  1220534 |     34228 |         1220534 |
| 4. ret_eom not null               |  1194978 |     28702 |         1194978 |
| 5. amount_outstanding > 0         |  1188051 |     28601 |         1188051 |

**Equity cleaning (common equity):**

| step                             |   n_rows |   n_permno |   n_permco |
|:---------------------------------|---------:|-----------:|-----------:|
| 0. raw msf_v2 (2015-01..2025-12) |  1109308 |      16912 |      10663 |
| 1. securitytype='EQTY'           |   704237 |       9668 |       9517 |
| 2. sharetype='NS'                |   634444 |       8768 |       8662 |
| 3. issuertype in {CORP,REIT}     |   634444 |       8768 |       8662 |
| 4. mthret not null               |   629624 |       8767 |       8661 |

**Bond→permco link:**
- bond_months_in: **1,188,051**
- bond_months_linked: **995,871**
- bond_months_unlinked: **192,180**
- ambiguous_multi_permco_bond_months_dropped: **1,564**
- bond_months_out: **994,307**
- n_permco_out: **1,434**
- null_link_startdt: **0**
- null_link_enddt: **0**

**Aggregation → panel (inner join on permco×month):**
- bond permco-months: **111,683**
- equity permco-months (firms in bond set): **130,362**
- **panel firm-months (bond ∩ equity): 98,373**
- bond permco-months with NO matching common-equity firm-month: **13,310** (11.9%)

## 2. Final sample & monthly firm coverage

- Firm-months: **98,373** | unique firms (permco): **1,244** | months: **2015-01 → 2025-11** (131 months)
- Firms per month: mean **751**, min 619 (2025-08), max 943 (2015-03)

## 3. Bonds per firm-month

```
{
"p5": 1.0,
"p25": 2.0,
"p50": 4.0,
"p75": 10.0,
"p90": 22.0,
"p95": 33.0,
"p99": 68.0,
"min": 1.0,
"max": 375.0,
"mean": 9.12184,
"n": 98373
}
```
- firm-months with exactly 1 bond: **20,467** (20.8%); with ≥2: 79.2%

## 4. AO-weight concentration (largest bond's share of firm AO)

```
{
"p1": 0.04494,
"p5": 0.07194,
"p25": 0.17249,
"p50": 0.33333,
"p75": 0.625,
"p95": 1.0,
"p99": 1.0,
"min": 0.02145,
"max": 1.0,
"mean": 0.44409,
"n": 98373
}
```
- firm-months where top bond ≥ 50% of AO: 36.9% (note: single-bond firm-months are 100% by construction)
- among firm-months with ≥2 bonds, top-bond weight: mean 0.298, p95 0.630

## 5. Missingness in panel columns

|                  |   n_missing |   pct_missing |
|:-----------------|------------:|--------------:|
| permco           |           0 |         0     |
| ym               |           0 |         0     |
| yyyymm           |           0 |         0     |
| date             |           0 |         0     |
| n_bonds          |           0 |         0     |
| bond_ao_total    |           0 |         0     |
| top_bond_wt      |           0 |         0     |
| frac_ig_ao       |           0 |         0     |
| bond_ret_ao      |           0 |         0     |
| bond_ret_ew      |           0 |         0     |
| bond_ret_med     |           0 |         0     |
| n_share_classes  |           0 |         0     |
| firm_mktcap      |           0 |         0     |
| siccd            |           0 |         0     |
| equity_ret       |           0 |         0     |
| equity_ret_fwd1  |          28 |         0.028 |
| bond_ret_ao_fwd1 |        1954 |         1.986 |

_Note: `equity_ret_fwd1` / `bond_ret_ao_fwd1` are forward TARGETS; missing at the last month of a firm's record (no t+1), which is expected, not look-ahead._

## 6. Return distributions

- **bond_ret_ao**: `{"p1": -0.09145, "p5": -0.03316, "p25": -0.00522, "p50": 0.00383, "p75": 0.01271, "p95": 0.04031, "p99": 0.08972, "min": -0.79164, "max": 2.82948, "mean": 0.00348, "n": 98373}`
- **bond_ret_ew**: `{"p1": -0.09116, "p5": -0.03236, "p25": -0.0051, "p50": 0.00386, "p75": 0.01268, "p95": 0.03942, "p99": 0.08813, "min": -0.79146, "max": 2.85654, "mean": 0.00351, "n": 98373}`
- **bond_ret_med**: `{"p1": -0.09135, "p5": -0.03163, "p25": -0.00395, "p50": 0.00345, "p75": 0.01162, "p95": 0.03823, "p99": 0.08868, "min": -0.78194, "max": 2.88013, "mean": 0.00334, "n": 98373}`
- **equity_ret**: `{"p1": -0.30556, "p5": -0.15238, "p25": -0.0458, "p50": 0.00756, "p75": 0.06069, "p95": 0.1726, "p99": 0.33873, "min": -0.87802, "max": 5.25472, "mean": 0.00927, "n": 98373}`
- **equity_ret_fwd1**: `{"p1": -0.31084, "p5": -0.15225, "p25": -0.04535, "p50": 0.00775, "p75": 0.06081, "p95": 0.17309, "p99": 0.33896, "min": -0.98017, "max": 5.25472, "mean": 0.00928, "n": 98345}`

- Corr(bond AO vs equity, contemporaneous): **0.424**
- Corr(AO vs EW): 0.988, Corr(AO vs median): 0.988

## 7. Integrity & no-look-ahead checks

- Unique (permco, ym) — one bond return + one equity return per firm-month: duplicates = **0** ✅
- Rows with a bond return: **98,373** / 98,373; with an equity return: **98,373** / 98,373 ✅
- Forward-return alignment: for consecutive firm-months, equity_ret_fwd1[t] == equity_ret[t+1] — mismatches = **0** of 96,416 ✅
- Bond signal month == equity return month by construction (merged on same ym) ✅
- Share-class weighting uses PRIOR-month cap (shift +1); no contemporaneous cap used as weight ✅
- Forward equity return present for last signal month (2025-11): 619 / 619 firms (sourced from 2025-12 CRSP)
