# Phase 4 — Candidate A backtest (gross + illustrative costs)

Generated 2026-10-03T03:25:17Z

Cross-sectional monthly long/short on the frozen no-look-ahead dislocation signal (`Dislocation_{i,t}=eq_t-(alpha_t+beta_t*bd_t)`, alpha/beta on s<=t-1). Quintiles (primary): LONG Q5, SHORT Q1, dollar-neutral, 1-month hold, monthly rebalance. Signal months 2017-01..2025-11.

**Weighting (two layers):** within firm = AO-weighted bonds (Phase 2); across firms = **equal-weight firms (PRIMARY)**; AO-across-firms (firm `bond_ao_total`) = robustness.
**Return:** credit-excess (duration-matched Treasury-hedged) = PRIMARY; raw bond return = robustness. All returns are additive monthly spreads (bond total/excess returns).

## Performance summary

| sleeve   | return_def    | port_weight   |   n_quantiles |   n_months |   mean_mo_% |   ann_ret_% |   ann_vol_% |   sharpe |   nw_tstat |   hit_rate |   maxDD_% |   skew |   turnover_% |   avg_n_long |   avg_n_short |
|:---------|:--------------|:--------------|--------------:|-----------:|------------:|------------:|------------:|---------:|-----------:|-----------:|----------:|-------:|-------------:|-------------:|--------------:|
| ALL      | credit_excess | AO_firms      |             5 |        106 |        0.26 |        3.15 |        3.02 |     1.04 |       2.66 |       60.4 |     -2.58 |   4.81 |       167.23 |     141.604  |      141.887  |
| HY       | credit_excess | AO_firms      |             5 |        106 |        0.48 |        5.81 |        9.21 |     0.63 |       1.76 |       60.4 |    -13.23 |   4.04 |       165.2  |      39.7453 |       40      |
| IG       | credit_excess | AO_firms      |             5 |        106 |        0.16 |        1.96 |        1.86 |     1.05 |       2.42 |       64.2 |     -2.23 |   3.91 |       165.29 |     102.028  |      102.198  |
| ALL      | credit_excess | EW_firms      |             5 |        106 |        0.43 |        5.1  |        4.13 |     1.24 |       2.8  |       71.7 |     -2.52 |   3.29 |       157.44 |     141.604  |      141.887  |
| HY       | credit_excess | EW_firms      |             5 |        106 |        0.84 |       10.06 |        9.1  |     1.1  |       2.79 |       68.9 |     -8.88 |   2.42 |       158.34 |      39.7453 |       40      |
| IG       | credit_excess | EW_firms      |             5 |        106 |        0.18 |        2.17 |        1.94 |     1.12 |       2.47 |       76.4 |     -1.08 |   4.92 |       159.73 |     102.028  |      102.198  |
| ALL      | raw_bond      | AO_firms      |             5 |        106 |        0.26 |        3.15 |        3.38 |     0.93 |       2.6  |       60.4 |     -3.01 |   3.49 |       167.22 |     141.802  |      142.038  |
| HY       | raw_bond      | AO_firms      |             5 |        106 |        0.46 |        5.57 |        8.91 |     0.62 |       1.77 |       58.5 |    -12.28 |   3.61 |       165.05 |      39.8774 |       40.1509 |
| IG       | raw_bond      | AO_firms      |             5 |        106 |        0.16 |        1.95 |        2.44 |     0.8  |       2.1  |       59.4 |     -2.81 |   2.09 |       165.26 |     102.047  |      102.198  |
| ALL      | raw_bond      | EW_firms      |             5 |        106 |        0.4  |        4.86 |        4.11 |     1.18 |       2.95 |       68.9 |     -2.87 |   2.61 |       157.34 |     141.802  |      142.038  |
| HY       | raw_bond      | EW_firms      |             5 |        106 |        0.77 |        9.3  |        8.78 |     1.06 |       2.99 |       68.9 |    -10.51 |   1.85 |       158.07 |      39.8774 |       40.1509 |
| IG       | raw_bond      | EW_firms      |             5 |        106 |        0.18 |        2.18 |        2.34 |     0.93 |       2.22 |       70.8 |     -1.78 |   2.61 |       159.71 |     102.047  |      102.198  |
| ALL      | credit_excess | EW_firms      |            10 |        106 |        0.6  |        7.2  |        6.61 |     1.09 |       2.63 |       67   |     -5.09 |   3.38 |       172.94 |      71.066  |       71.217  |
| HY       | credit_excess | EW_firms      |            10 |        106 |        1    |       11.94 |       12.38 |     0.96 |       2.63 |       64.2 |    -21.58 |   0.77 |       174.07 |      20.1509 |       20.3019 |
| IG       | credit_excess | EW_firms      |            10 |        106 |        0.26 |        3.17 |        2.88 |     1.1  |       2.43 |       67   |     -1.39 |   5    |       176.61 |      51.2642 |       51.3396 |

_`turnover_%` = average one-sided turnover per rebalance (0.5·Σ|Δw|). Returns are monthly L/S spreads; ann. figures = mean×12 and sd×√12; Sharpe = ann_ret/ann_vol; `nw_tstat` = Newey-West (3 lag) t-stat of the monthly mean; maxDD on cumulative additive spread._

## Duration-gap diagnostic (primary quintiles)

AO-weighted duration difference Q5−Q1 (years). Credit-excess returns already Treasury-hedge each leg; a small gap confirms the L/S is not a duration bet.

| sleeve   |   mean_dur_gap_Q5_minus_Q1_yrs |   std_dur_gap_yrs |
|:---------|-------------------------------:|------------------:|
| ALL      |                          0.089 |             1.314 |
| HY       |                          0.049 |             0.491 |
| IG       |                         -0.043 |             1.378 |

## Transaction-cost sensitivity — ILLUSTRATIVE ONLY

**These bp levels are illustrative assumptions, NOT estimated transaction costs.** `t_spread` is not used (its meaning is unverified; it is not a confirmed bid-ask measure), and we have no defensible observed executable bid-ask for these bonds. Monthly cost drag = (cost_bp/1e4) × 2 × one-sided turnover (both legs). Primary portfolios (credit-excess, EW firms, quintiles):

| sleeve   |   illustrative_cost_bp_roundtrip |   mo_cost_drag_% |   net_ann_ret_% |   net_sharpe |   net_mean_mo_% |
|:---------|---------------------------------:|-----------------:|----------------:|-------------:|----------------:|
| ALL      |                                0 |            0     |            5.1  |         1.24 |           0.425 |
| ALL      |                               10 |            0.315 |            1.33 |         0.32 |           0.11  |
| ALL      |                               25 |            0.787 |           -4.34 |        -1.05 |          -0.362 |
| ALL      |                               50 |            1.574 |          -13.79 |        -3.34 |          -1.149 |
| ALL      |                              100 |            3.149 |          -32.68 |        -7.92 |          -2.724 |
| HY       |                                0 |            0     |           10.06 |         1.1  |           0.838 |
| HY       |                               10 |            0.317 |            6.26 |         0.69 |           0.521 |
| HY       |                               25 |            0.792 |            0.56 |         0.06 |           0.046 |
| HY       |                               50 |            1.583 |           -8.94 |        -0.98 |          -0.745 |
| HY       |                              100 |            3.167 |          -27.94 |        -3.07 |          -2.329 |
| IG       |                                0 |            0     |            2.17 |         1.12 |           0.18  |
| IG       |                               10 |            0.319 |           -1.67 |        -0.86 |          -0.139 |
| IG       |                               25 |            0.799 |           -7.42 |        -3.83 |          -0.618 |
| IG       |                               50 |            1.597 |          -17    |        -8.79 |          -1.417 |
| IG       |                              100 |            3.195 |          -36.17 |       -18.69 |          -3.014 |

## Caveats (carry into the pitch)

- This is a **bond** trade exploiting a robust predictive relation `eq_t→bd_{t+1}`; it is **not** proof of causal information diffusion.
- Per-name edge is modest; the strategy needs breadth and low costs. Single-name cash-bond **shorting is impractical/expensive in reality** — Candidate A is the research/backtest vehicle; real-world expression would use CDS/CDX/ETF (untested here).
- The relation may invert in liquidity/crisis regimes (correlations spike, bonds gap).
- Cost levels above are illustrative; realistic costs are higher in HY than IG.
