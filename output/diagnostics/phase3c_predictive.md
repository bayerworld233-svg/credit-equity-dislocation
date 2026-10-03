# Phase 3c — Predictive tests

Generated 2026-10-03T01:15:56Z

Signal firm-months (with valid t+1 equity): 76,557 | firms 1,066 | signal months 2017-01..2025-11 (107)

| specification                                           |   coef(gamma/delta) |     se |   t_stat |   p_value |     N |   +1SD_effect_bp |
|:--------------------------------------------------------|--------------------:|-------:|---------:|----------:|------:|-----------------:|
| PRIMARY: eq_{t+1} ~ dislocation + month FE              |             -0.0273 | 0.019  |    -1.44 |    0.1498 | 76557 |            -29.5 |
| context: eq_{t+1} ~ dislocation (pooled, no FE)         |             -0.0425 | 0.0434 |    -0.98 |    0.3277 | 76557 |            -45.8 |
| REVERSE diagnostic: bond_{t+1} ~ dislocation + month FE |              0.0303 | 0.0107 |     2.84 |    0.0045 | 75028 |             32.5 |
| context: bond_{t+1} ~ dislocation (pooled, no FE)       |              0.0278 | 0.0163 |     1.71 |    0.0879 | 75028 |             29.9 |

_`+1SD_effect_bp` = coefficient × SD(dislocation), i.e. basis-point change in the next-month return from a one-standard-deviation increase in dislocation._

Interpretation guide (empirical, not assumed): primary gamma<0 ⇒ equity reverts toward the bond-implied level (convergence / bonds-lead). Reverse delta≈0 with gamma<0 ⇒ bonds lead equities; delta large with gamma≈0 ⇒ equities lead bonds.
