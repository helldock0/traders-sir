# NAS100 v3 range breakout - backtest

Data: Dukascopy US100 CFD, 5-minute bid/ask, 2011-09-18 to 2026-10-07 (the 07:00-10:00 New York range only exists from 2013-05). Rules: strategies/user/nas100_orb_v3.py.
Costs: spread in the fills, 1 pt slippage per market/stop fill, no commission, overnight financing (Fed funds +/- 2.5 %/yr). R = net result divided by the stop distance.

## Day counts

Weekdays 3804; range incomplete (no data / holidays) 423; no confirmed break by 16:55 264; skip rule fired 0; confirmed breaks 3117; traded 2674 (the rest came while a trade was open); failed confirmations 1249.

## Results as written (net of costs)

| period | trades | win % | avg R | t | total R | profit factor | max drawdown R | longest losing run |
|---|---|---|---|---|---|---|---|---|
| 2013-05 to 2017 | 888 | 15.7 | -0.342 | -5.50 | -304.1 | 0.64 | 307.4 | 31 |
| 2018-2023 | 1243 | 22.5 | +0.075 | +1.26 | +93.6 | 1.09 | 42.1 | 18 |
| 2024-2026 | 543 | 22.5 | +0.061 | +0.68 | +33.2 | 1.07 | 38.5 | 20 |
| all | 2674 | 20.2 | -0.066 | -1.69 | -177.3 | 0.92 | 324.4 | 31 |

## Frictionless (no spread, slippage or financing)

| period | trades | win % | avg R | t | total R | profit factor | max drawdown R | longest losing run |
|---|---|---|---|---|---|---|---|---|
| 2013-05 to 2017 | 877 | 21.0 | +0.010 | +0.14 | +9.2 | 1.01 | 59.5 | 23 |
| 2018-2023 | 1238 | 23.7 | +0.178 | +2.93 | +220.4 | 1.23 | 27.0 | 21 |
| 2024-2026 | 541 | 24.4 | +0.194 | +2.08 | +105.1 | 1.25 | 36.2 | 18 |
| all | 2656 | 23.0 | +0.126 | +3.01 | +334.6 | 1.16 | 59.5 | 23 |

## By year

| year | trades | win % | avg R net | total R net | avg R frictionless | avg stop (points) | avg spread at entry (points) | financing R per trade |
|---|---|---|---|---|---|---|---|---|
| 2013 | 96 | 12.5 | -0.571 | -54.8 | -0.158 | 7.6 | 1.88 | -0.018 |
| 2014 | 182 | 11.5 | -0.540 | -98.4 | -0.056 | 10.9 | 1.93 | -0.016 |
| 2015 | 199 | 19.6 | -0.120 | -23.8 | +0.152 | 13.3 | 1.17 | -0.017 |
| 2016 | 214 | 15.4 | -0.352 | -75.3 | -0.163 | 12.7 | 0.97 | -0.013 |
| 2017 | 197 | 17.3 | -0.263 | -51.9 | +0.204 | 10.9 | 1.08 | -0.028 |
| 2018 | 212 | 21.2 | -0.003 | -0.7 | +0.200 | 25.2 | 1.00 | -0.015 |
| 2019 | 202 | 21.8 | -0.016 | -3.2 | +0.135 | 20.8 | 0.99 | -0.023 |
| 2020 | 217 | 23.0 | +0.117 | +25.3 | +0.203 | 47.0 | 1.34 | -0.014 |
| 2021 | 202 | 23.8 | +0.152 | +30.8 | +0.219 | 49.7 | 1.25 | -0.017 |
| 2022 | 206 | 22.3 | +0.087 | +17.9 | +0.162 | 75.5 | 1.22 | -0.009 |
| 2023 | 204 | 23.0 | +0.115 | +23.5 | +0.147 | 49.9 | 1.25 | -0.015 |
| 2024 | 192 | 22.9 | +0.101 | +19.3 | +0.332 | 61.8 | 1.37 | -0.031 |
| 2025 | 202 | 19.8 | -0.081 | -16.4 | +0.034 | 81.4 | 1.33 | -0.023 |
| 2026 | 149 | 25.5 | +0.204 | +30.3 | +0.234 | 104.7 | 1.09 | -0.021 |

## Stress: +1 point spread per trade

| period | trades | win % | avg R | t | total R | profit factor | max drawdown R | longest losing run |
|---|---|---|---|---|---|---|---|---|
| 2013-05 to 2017 | 888 | 15.7 | -0.449 | -7.19 | -398.8 | 0.57 | 399.0 | 31 |
| 2018-2023 | 1243 | 22.5 | +0.042 | +0.71 | +52.4 | 1.05 | 52.1 | 18 |
| 2024-2026 | 543 | 22.5 | +0.046 | +0.51 | +24.7 | 1.05 | 40.1 | 20 |
| all | 2674 | 20.2 | -0.120 | -3.05 | -321.7 | 0.87 | 434.4 | 31 |

## Skip-rule readings (net)

as_written: buy skipped if the confirming close < break low - 2 (sell: > break high + 2). chase: buy skipped if the confirming close > break high + 2 (sell: < break low - 2). off: no filter.

| reading / period | trades | win % | avg R | t | total R | profit factor | max drawdown R | longest losing run |
|---|---|---|---|---|---|---|---|---|
| as_written (0 skips) 2018-2023 | 1243 | 22.5 | +0.075 | +1.26 | +93.6 | 1.09 | 42.1 | 18 |
| as_written (0 skips) 2024-2026 | 543 | 22.5 | +0.061 | +0.68 | +33.2 | 1.07 | 38.5 | 20 |
| as_written (0 skips) all | 2674 | 20.2 | -0.066 | -1.69 | -177.3 | 0.92 | 324.4 | 31 |
| chase (1114 skips) 2018-2023 | 771 | 23.0 | +0.089 | +1.17 | +68.9 | 1.11 | 33.6 | 18 |
| chase (1114 skips) 2024-2026 | 307 | 23.5 | +0.104 | +0.85 | +31.9 | 1.13 | 39.8 | 17 |
| chase (1114 skips) all | 1782 | 19.8 | -0.098 | -2.05 | -175.5 | 0.89 | 293.3 | 27 |
| off (0 skips) 2018-2023 | 1243 | 22.5 | +0.075 | +1.26 | +93.6 | 1.09 | 42.1 | 18 |
| off (0 skips) 2024-2026 | 543 | 22.5 | +0.061 | +0.68 | +33.2 | 1.07 | 38.5 | 20 |
| off (0 skips) all | 2674 | 20.2 | -0.066 | -1.69 | -177.3 | 0.92 | 324.4 | 31 |

## Long vs short (net, 2018-2026)

| side | trades | win % | avg R | t | total R | profit factor | max drawdown R | longest losing run |
|---|---|---|---|---|---|---|---|---|
| long | 989 | 24.9 | +0.169 | +2.44 | +166.7 | 1.21 | 26.2 | 17 |
| short | 797 | 19.6 | -0.050 | -0.70 | -39.9 | 0.94 | 73.3 | 25 |

## Holding

Median hold 2.2 h, mean 15.1 h, 90th percentile 55.5 h, longest 11.0 days; 35% of trades held overnight; exits: {'END': 1, 'SL': 2133, 'TP': 540}; average financing -0.018 R per trade.

## Alpha Swing $10k (phase 1 +10 %, phase 2 +5 %, 5 % daily on equity, 10 % max)

| risk per trade | starts from | challenges | pass <= 1m % | pass <= 2m % | fail <= 2m % | pass eventually % | median months to pass |
|---|---|---|---|---|---|---|---|
| 0.5% | 2018 | 1589 | 0.0 | 0.3 | 3.0 | 49.1 | 9.7 |
| 0.5% | 2021 | 959 | 0.0 | 0.5 | 1.9 | 47.2 | 9.2 |
| 1.0% | 2018 | 1589 | 4.8 | 15.5 | 37.7 | 34.2 | 2.2 |
| 1.0% | 2021 | 959 | 5.8 | 19.3 | 37.2 | 39.4 | 2.0 |
| 1.5% | 2018 | 1589 | 12.8 | 23.9 | 65.3 | 28.4 | 1.1 |
| 1.5% | 2021 | 959 | 14.1 | 27.2 | 63.0 | 31.8 | 1.1 |
| 2.0% | 2018 | 1589 | 14.7 | 18.4 | 80.5 | 18.8 | 0.7 |
| 2.0% | 2021 | 959 | 15.3 | 18.5 | 80.5 | 18.6 | 0.7 |
