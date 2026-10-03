# Phase 1 Data Audit

Generated: 2026-10-02T23:28:57Z

Raw sources (see `data/raw/_manifest.json` for SQL + hashes):

- bondret: **3,153,572** rows | equity_msf_v2: **1,109,308** | bondcrsp_link: **383,120** | ff_factors: **132**


## 1. Corporate bonds — `wrdsapps_bondret.bondret`

- Date range: **2015-01-31 → 2025-11-30**
- Unique bond CUSIPs: **160,526** | unique issuers (`company_symbol`): **2,062**
- Duplicate (cusip, date) rows: **0** (expected key = cusip×date)

**Missingness (key columns):**

| column             |   n_missing |   pct_missing |
|:-------------------|------------:|--------------:|
| ret_eom            |      146911 |         4.659 |
| ret_ldm            |     2467462 |        78.243 |
| ret_l5m            |     2138623 |        67.816 |
| price_eom          |           0 |         0     |
| yield              |       24198 |         0.767 |
| t_spread           |     1700870 |        53.935 |
| coupon             |        2043 |         0.065 |
| duration           |       34148 |         1.083 |
| tmt                |        7409 |         0.235 |
| amount_outstanding |        2197 |         0.07  |
| rating_num         |     1715222 |        54.39  |
| rating_class       |           0 |         0     |
| rating_cat         |           0 |         0     |
| maturity           |           0 |         0     |

**Units / distribution of key numeric variables** (infer units from magnitudes):

|                    |       0.001 |       0.01 |        0.05 |           0.25 |           0.5 |            0.75 |        0.95 |        0.99 |          0.999 |            min |             max |              mean |           n |
|:-------------------|------------:|-----------:|------------:|---------------:|--------------:|----------------:|------------:|------------:|---------------:|---------------:|----------------:|------------------:|------------:|
| ret_eom            | -0.31897    |  -0.102668 |  -0.0309857 |    0           |    0          |      0.00524524 |   0.0533913 |   0.16316   |    0.495359    |  -0.999498     |  154.15         |      0.00554822   | 3.00666e+06 |
| yield              | -1          |  -0.7201   |  -0.223181  |    0           |    0.0115343  |      0.0445709  |   0.0729291 |   0.312431  |    4.88359     | -11.9985       |    5.99261e+166 |      1.91589e+160 | 3.12937e+06 |
| t_spread           |  0          |   0        |   0         |    0.000977253 |    0.00216581 |      0.00417353 |   0.010432  |   0.0206986 |    0.0527484   |   0            |    1.92196      |      0.0034296    | 1.4527e+06  |
| coupon             |  0          |   0        |   0         |    0           |    0          |      4.15       |   7         |   8.875     |   13           |   0            |   33.75         |      2.05794      | 3.15153e+06 |
| duration           |  0.0139385  |   0.191491 |   0.563812  |    1.65483     |    3.18693    |      5.3422     |  14.0391    |  17.3884    |   86.7677      |   4.63534e-170 |    7.2558e+14   |      2.66395e+09  | 3.11942e+06 |
| tmt                |  0.00833333 |   0.130556 |   0.463889  |    1.56944     |    3.20833    |      5.83611    |  24.3722    |  30.0583    |   81.0389      |   0            |  102.133        |      5.80461      | 3.14616e+06 |
| amount_outstanding |  0          | 100        | 350         | 1408           | 6236          | 393179          |   1.25e+06  |   2.5e+06   |    4.49247e+06 |  -7.4775e+06   |    1.14065e+07  | 262771            | 3.15138e+06 |
| price_eom          |  6.38558    |   8.85667  |   9.95025   |   95.6275      |   99.875      |    105.763      | 134.06      | 172.2       | 1293.67        |   1e-06        | 9989.51         |     98.0622       | 3.15357e+06 |
| rating_num         |  1          |   2        |   4         |    6           |    7          |      9          |  13         |  16         |   20           |   1            |   22            |      7.6921       | 1.43835e+06 |
- |ret_eom| > 50%: **3,735** obs (0.1242%)
- |ret_eom| > 100%: **412** obs (0.0137%)
- |ret_eom| > 200%: **82** obs (0.0027%)

**rating_class composition (IG/HY split):**

| rating_class   |       n |   pct |
|:---------------|--------:|------:|
| 1.HY           | 1847034 | 58.57 |
| 0.IG           | 1306538 | 41.43 |

**Bonds per issuer-month (raw, by `company_symbol`):**
- mean 19.69, median 3, p90 20, p99 228, max 4781

### 1b. Price staleness & characteristic data quality (key finding)

- `price_eom_flg`: **Current 1,698,635** (53.9%) vs **CryFwd (carried-forward/stale) 1,454,937** (46.1%)
- `ret_eom` exactly == 0: **1,290,555** (42.9% of all rows)
- Zero-return rate | CryFwd = **88.6%** vs | Current = **0.07%** (→ the zero-return mass is stale carried-forward prices)

**Staleness & missingness by `bond_type`** (CDEB=debentures, CMTZ=medium-term notes, CMTN=MTN):

| bond_type   |       n |   pct_rows |   cryfwd_rate |   zero_ret_rate |   ret_na_rate |
|:------------|--------:|-----------:|--------------:|----------------:|--------------:|
| CMTZ        | 1761479 |      55.86 |          73.1 |            78.5 |           6.8 |
| CDEB        | 1117008 |      35.42 |           5.3 |             0.1 |           1   |
| CMTN        |  275078 |       8.72 |          39.4 |             0.5 |           5.9 |
| CP          |       7 |       0    |          57.1 |            50   |          14.3 |

**Characteristic data-quality flags (counts of implausible values):**
- `yield` (decimal units; median 0.0277): **710,986 negative** (22.7%), **10,278 > 100%**, max = 5.99e+166 (CORRUPT — field unreliable)
- `duration` (years): 3,898 > 40yr, 3,026 > 100 (max 7.26e+14); **99.88% plausible [0,40]**
- `amount_outstanding` ($thousands): 34 negative, 11,923 zero (minor)
- `coupon`: 55.9% == 0, almost all `bond_type=CMTZ` (zero/structured MTNs)


## 2. Equities — `crsp.msf_v2` (CRSP v2 monthly)

- Date range: **2015-01-30 → 2025-12-31**
- Unique permno: **16,912** | permco: **10,663**
- Duplicate (permno, mthcaldt) rows: **0**

**Missingness (key columns):**

| column   |   n_missing |   pct_missing |
|:---------|------------:|--------------:|
| mthret   |        5152 |         0.464 |
| mthretx  |        5152 |         0.464 |
| mthcap   |        4652 |         0.419 |
| mthprc   |        4652 |         0.419 |
| shrout   |           0 |         0     |
| siccd    |           0 |         0     |
| cusip    |           0 |         0     |
| mthvol   |        4652 |         0.419 |

**Units / distribution:**

|         |      0.001 |        0.01 |         0.05 |          0.25 |              0.5 |            0.75 |             0.95 |          0.99 |          0.999 |     min |              max |            mean |           n |
|:--------|-----------:|------------:|-------------:|--------------:|-----------------:|----------------:|-----------------:|--------------:|---------------:|--------:|-----------------:|----------------:|------------:|
| mthret  |  -0.756406 |   -0.409081 |    -0.207515 |     -0.047368 |      0.003415    |     0.047379    |      0.204168    |   0.507448    |    1.55866     | -1      |     39           |     0.0054901   | 1.10416e+06 |
| mthretx |  -0.75822  |   -0.41018  |    -0.208661 |     -0.04936  |      0.001404    |     0.045304    |      0.203001    |   0.50666     |    1.55866     | -1      |     39           |     0.00367188  | 1.10416e+06 |
| mthprc  |   0.128065 |    0.3938   |     1.3      |      9.7      |     22.92        |    44.25        |    127           | 300.314       | 1237.89        |  0.0006 | 800540           |    88.4159      | 1.10466e+06 |
| mthcap  | 520.104    | 1986.18     |  6534        |  68919.9      | 342804           |     1.86782e+06 |      2.04983e+07 |   9.32717e+07 |    4.28544e+08 | 21.6    |      4.92152e+09 |     5.84059e+06 | 1.10466e+06 |
| shrout  |  20        |  100        |   350        |   6442        |  26163           | 75390           | 371988           |   1.25841e+06 |    4.70393e+06 |  2      |      2.45688e+07 | 99751           | 1.10931e+06 |
| mthvol  |  27        | 2603        | 27002        | 499086        |      3.02845e+06 |     1.45299e+07 |      9.526e+07   |   3.55723e+08 |    1.42196e+09 |  0      |      1.73781e+10 |     2.44272e+07 | 1.10466e+06 |

- Negative `mthprc` values (CRSP bid/ask-avg convention): **0** (0.000%)
- |mthret| > 50%: **17,315** (1.5682%)
- |mthret| > 100%: **2,723** (0.2466%)
- |mthret| > 200%: **682** (0.0618%)

**`mthdelflg` (delisting flag) composition:**

| mthdelflg   |       n |
|:------------|--------:|
| N           | 1103081 |
| A           |    4738 |
| P           |    1213 |
| M           |     159 |
| V           |     104 |
| G           |      13 |

**`sharetype` composition:**

| sharetype   |       n |   pct |
|:------------|--------:|------:|
| NS          | 1002215 | 90.35 |
| AD          |   50371 |  4.54 |
| SB          |   42288 |  3.81 |
| UG          |   14357 |  1.29 |
| CE          |      77 |  0.01 |

**`securitytype` composition:**

| securitytype   |      n |   pct |
|:---------------|-------:|------:|
| EQTY           | 704237 | 63.48 |
| FUND           | 405071 | 36.52 |

**`issuertype` composition:**

| issuertype   |      n |   pct |
|:-------------|-------:|------:|
| CORP         | 675686 | 60.91 |
| ACOR         | 405071 | 36.52 |
| REIT         |  28551 |  2.57 |

**`mthretflg` composition (return availability/missing-code):**

| mthretflg   |       n |
|:------------|--------:|
| CR          | 1087843 |
| NS          |    9203 |
| DE          |    6210 |
| NT          |    5152 |
| MP          |     404 |
| IP          |     297 |
| GP          |     199 |


## 3. Official bond↔CRSP link — `wrdsapps_link_crsp_bond.bondcrsp_link`

- Rows: **383,120** | unique bond CUSIP: **376,524** | unique permno: **4,147** | permco: **4,075**
- link_startdt range: 2002-07-01 → 2025-12-31; link_enddt max: 2025-12-31
- Bond CUSIPs mapping to >1 permno across history: **3,719** (0.99%)


## 4. Mapping quality: bondret → permno (point-in-time)

- Bond-months total: **3,153,572**; linked to >=1 permno: **2,636,729** (**83.61%**)
- Ambiguous bond-months (match >1 permno at once): **1,591** (0.060% of linked)
- Bond CUSIPs never linked in-window: **62,988** of 160,526

**Link rate by year:**

|   year |   bond_months |   linked |   link_rate_pct |
|-------:|--------------:|---------:|----------------:|
|   2015 |        178462 |   146704 |           82.2  |
|   2016 |        194152 |   157632 |           81.19 |
|   2017 |        209842 |   169368 |           80.71 |
|   2018 |        235631 |   194172 |           82.41 |
|   2019 |        263224 |   219625 |           83.44 |
|   2020 |        292179 |   244020 |           83.52 |
|   2021 |        303373 |   256425 |           84.52 |
|   2022 |        339435 |   294664 |           86.81 |
|   2023 |        379341 |   321981 |           84.88 |
|   2024 |        400249 |   336910 |           84.18 |
|   2025 |        357684 |   295228 |           82.54 |

- Linked firms per month: mean **878**, min 717, max 1111
- Bonds per firm-month (linked): mean 22.91, median 4, p90 23, p99 335, max 4335

### 4b. Firm cross-section under candidate universe restrictions (diagnostic)

_Shows how the linked **firm** cross-section holds up when stale/illiquid bonds are excluded. Evidence for a Phase-2 decision, not a filter chosen here._

| universe           |   bond_months |   linked_bond_months |   firms_per_month_mean |   firms_per_month_min |   bonds_per_firm_mean |   bonds_per_firm_median |
|:-------------------|--------------:|---------------------:|-----------------------:|----------------------:|----------------------:|------------------------:|
| ALL (raw)          |       3153572 |              2636729 |                    878 |                   717 |                  22.9 |                       4 |
| Current price only |       1698635 |              1345324 |                    861 |                   710 |                  11.9 |                       4 |
| CDEB only          |       1117008 |               915902 |                    867 |                   706 |                   8.1 |                       4 |
| Current + CDEB     |       1057966 |               875584 |                    849 |                   702 |                   7.9 |                       4 |


## 5. Fama-French factors — `ff.factors_monthly`

- Date range: 2015-01-01 → 2025-12-01; rows: 132 (cols: date, mktrf, smb, hml, umd, rf)
