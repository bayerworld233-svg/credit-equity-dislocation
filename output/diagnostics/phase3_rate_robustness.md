# Phase 3 — Rate/Duration & IG-HY robustness

Generated 2026-10-03T02:24:04Z

Sample: 2017-01..2025-11; signal firm-months with bd_(t+1): 75,028; with AO-duration: 76,499 (99.9%); with credit-excess bd_(t+1): 74,957.
IG firm-months (frac_ig_ao>=0.5): 54,888; HY: 21,687

Coefficient on **eq_t** (the equity->bond effect `d`), signal-month FE + two-way clustered SE:

| spec                                  |   d(eq_t) |     se |    t |      p |   +1SD_bp |     N |
|:--------------------------------------|----------:|-------:|-----:|-------:|----------:|------:|
| Baseline (ALL): bd_(t+1)~bd_t+eq_t    |    0.0301 | 0.0105 | 2.87 | 0.0041 |      35.6 | 75028 |
| Spec A (ALL): +AOdur+AOdur*Dy10_(t+1) |    0.0305 | 0.0103 | 2.97 | 0.003  |      36   | 74967 |
| Spec B (ALL): credit-excess bd        |    0.0296 | 0.01   | 2.96 | 0.0031 |      34.9 | 74921 |
| Baseline (IG): bd_(t+1)~bd_t+eq_t     |    0.0114 | 0.0038 | 3    | 0.0027 |       9.9 | 53982 |
| Spec A (IG): +AOdur+AOdur*Dy10_(t+1)  |    0.0104 | 0.0035 | 2.98 | 0.0029 |       9   | 53973 |
| Spec B (IG): credit-excess bd         |    0.0115 | 0.0035 | 3.29 | 0.001  |      10   | 53966 |
| Baseline (HY): bd_(t+1)~bd_t+eq_t     |    0.0359 | 0.0127 | 2.84 | 0.0046 |      62.9 | 21046 |
| Spec A (HY): +AOdur+AOdur*Dy10_(t+1)  |    0.0382 | 0.0124 | 3.08 | 0.0021 |      66.9 | 20994 |
| Spec B (HY): credit-excess bd         |    0.0356 | 0.0123 | 2.9  | 0.0037 |      62   | 20955 |

_`+1SD_bp` = d x SD(eq_t) in basis points. Dy10_(t+1) is a realized t+1 control (ex-post), not a tradable time-t predictor. Duration-matched Treasury return interpolated linearly across the 1/2/5/7/10/20/30y points by duration-in-years (np.interp clamps bonds beyond the grid to the endpoints)._

**Interpretation (bounded):** if `d` survives Spec A/B, differential Treasury-rate exposure alone is unlikely to explain the equity->bond result, making a corporate-bond-specific / credit-related channel more plausible. The adjusted return still contains credit-spread, liquidity, and convexity effects, so this is NOT proof of a pure credit channel. IG/HY results are descriptive/mechanism-supporting, not proof.
