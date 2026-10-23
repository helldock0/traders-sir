# Post-hoc diagnostics (pre-registered K1-K5) for vix_state_gotobi_fix_reversal

Market cut at 2024-01-01 (holdout locked); costs = pipeline defaults; stats per arm from a fresh backtest of the reviewed module (identical to the stage A cells in research.sqlite).

## Stage A cells in research.sqlite

| arm | n all | avg R all | t all | design n | design avg R | design t | check n | check avg R | check t |
|---|---|---|---|---|---|---|---|---|---|
| all | 936 | +0.119 | 3.38 | 504 | +0.132 | 2.69 | 432 | +0.104 | 2.05 |
| atr | 415 | +0.157 | 2.62 | 219 | +0.158 | 1.80 | 196 | +0.157 | 1.94 |
| atr_vix | 206 | +0.068 | 0.74 | 83 | +0.048 | 0.26 | 123 | +0.081 | 0.93 |
| atr_vixlo | 209 | +0.246 | 3.16 | 136 | +0.225 | 2.68 | 73 | +0.284 | 1.79 |
| natr_vix | 198 | +0.162 | 2.17 | 101 | +0.205 | 2.09 | 97 | +0.117 | 1.03 |
| natr_vixlo | 323 | +0.044 | 0.90 | 184 | +0.063 | 0.95 | 139 | +0.020 | 0.27 |
| atr_or_vix | 613 | +0.159 | 3.37 | 320 | +0.173 | 2.56 | 293 | +0.144 | 2.18 |
| ng_vix | 1056 | +0.002 | 0.06 | 495 | +0.062 | 1.40 | 561 | -0.051 | -1.25 |
| ng_vixlo | 1390 | -0.031 | -1.27 | 822 | -0.011 | -0.33 | 568 | -0.060 | -1.70 |

## design: per-arm stats (net of costs; gross in brackets)

| arm | n | avg R net | t | avg R gross | trades/month |
|---|---|---|---|---|---|
| all | 504 | +0.132 | 2.69 | +0.168 | 6.0 |
| atr | 219 | +0.158 | 1.80 | +0.186 | 2.6 |
| atr_vix | 83 | +0.048 | 0.26 | +0.076 | 1.0 |
| atr_vixlo | 136 | +0.225 | 2.68 | +0.253 | 1.6 |
| natr_vix | 101 | +0.205 | 2.09 | +0.245 | 1.2 |
| natr_vixlo | 184 | +0.063 | 0.95 | +0.106 | 2.2 |
| atr_or_vix | 320 | +0.173 | 2.56 | +0.204 | 3.8 |
| ng_vix | 495 | +0.062 | 1.40 | +0.097 | 5.9 |
| ng_vixlo | 822 | -0.011 | -0.33 | +0.025 | 9.8 |

Stratified VIX effect E (design): net +0.003 R (month-cluster SE 0.123), gross +0.002 R; within-strata: ATR-high -0.177, ATR-low +0.142 (weights 0.43 / 0.57); gotobi VIX effect (V+ minus V- over all gotobi trades) +0.002 (SE 0.124); placebo effect (ng_vix minus ng_vixlo) +0.073 (SE 0.059); counts {'atr_vix': 83, 'atr_vixlo': 136, 'natr_vix': 101, 'natr_vixlo': 184, 'ng_vix': 495, 'ng_vixlo': 822}

## Kill rules (design)

- K1 (E >= +0.10 R and both strata > 0): E +0.003, ATR-high diff -0.177, ATR-low diff +0.142 -> KILL
- K2 (union t > atr t, natr_vix > natr_vixlo): union t 2.56 vs atr t 1.80; natr_vix +0.205 vs natr_vixlo +0.063 -> PASS
- K3 (gotobi effect minus placebo effect >= +0.05): +0.002 - (+0.073) = -0.071 -> KILL

## check: per-arm stats (net of costs; gross in brackets)

| arm | n | avg R net | t | avg R gross | trades/month |
|---|---|---|---|---|---|
| all | 432 | +0.104 | 2.05 | +0.148 | 6.0 |
| atr | 196 | +0.157 | 1.94 | +0.192 | 2.7 |
| atr_vix | 123 | +0.081 | 0.93 | +0.117 | 1.7 |
| atr_vixlo | 73 | +0.284 | 1.79 | +0.318 | 1.0 |
| natr_vix | 97 | +0.117 | 1.03 | +0.169 | 1.3 |
| natr_vixlo | 139 | +0.020 | 0.27 | +0.071 | 1.9 |
| atr_or_vix | 293 | +0.144 | 2.18 | +0.184 | 4.1 |
| ng_vix | 561 | -0.051 | -1.25 | -0.009 | 7.8 |
| ng_vixlo | 568 | -0.060 | -1.70 | -0.014 | 7.9 |

Stratified VIX effect E (check): net -0.039 R (month-cluster SE 0.112), gross -0.038 R; within-strata: ATR-high -0.202, ATR-low +0.097 (weights 0.45 / 0.55); gotobi VIX effect (V+ minus V- over all gotobi trades) -0.014 (SE 0.102); placebo effect (ng_vix minus ng_vixlo) +0.008 (SE 0.054); counts {'atr_vix': 123, 'atr_vixlo': 73, 'natr_vix': 97, 'natr_vixlo': 139, 'ng_vix': 561, 'ng_vixlo': 568}

## K4 (check)

- E in check -0.039 (> 0 needed); union check t 2.18 vs atr check t 1.94 -> KILL

## Verdict under the pre-registration

Design rules: at least one kill. The pipeline's 'candidate' status for the union cell reflects the gotobi edge itself (the 'atr' and 'all' arms pass the same gates); only K1-K4 decide whether the VIX state adds anything.
