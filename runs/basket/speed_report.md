# USDJPY basket: sizing for a pass within 60 days (Alpha Swing $10k)

Rules: Alpha Capital Group Alpha Swing; daily loss on the closed balance (floating = stress); day resets 17:00 New York; challenge starts up to 2025-10-07; fee placeholder $100 per attempt. Goal: {'pass_le_2m_min_pct': 50.0, 'fail_le_2m_max_pct': 15.0, 'pass_eventually_min_pct': 60.0, 'rank_by': 'pass_le_2m_pct', 'window': '2018', 'objective': 'pass within 60 days'}

## Family A: 32 static mixes on the 2018 window, closed rule. Mixes meeting the goal: 0

Sorted by pass <= 2m. Risk per leg in percent of balance.

| mix | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | median months to pass | months per funded | fees per funded $ | fail daily % |
|---|---|---|---|---|---|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 4% / m3 4% | 7 | 29 | 8 | 41 | 16 | 77 | 2.7 | 6.3 | 130 | 0 |
| vol_box 0.5% / vol_gotobi 4% / m3 4% | 10 | 29 | 18 | 36 | 31 | 59 | 2.0 | 6.8 | 170 | 10 |
| vol_box 0.5% / vol_gotobi 4% / m3 3% | 10 | 29 | 18 | 35 | 32 | 55 | 1.9 | 7.4 | 183 | 10 |
| vol_box 0.25% / vol_gotobi 4% / m3 3% | 7 | 27 | 8 | 40 | 15 | 74 | 2.8 | 6.9 | 135 | 0 |
| vol_box 0.25% / vol_gotobi 4% / fade 0.5% / m3 4% | 10 | 25 | 19 | 33 | 36 | 57 | 2.3 | 5.2 | 176 | 19 |
| vol_box 0.25% / vol_gotobi 4% / fade 0.5% / m3 3% | 10 | 24 | 18 | 33 | 38 | 54 | 2.3 | 5.8 | 186 | 17 |
| vol_box 0.5% / vol_gotobi 3% / m3 3% | 6 | 24 | 8 | 34 | 15 | 71 | 3.1 | 7.5 | 142 | 0 |
| vol_box 0.5% / vol_gotobi 3% / fade 0.5% / m3 4% | 8 | 23 | 18 | 31 | 33 | 63 | 3.1 | 5.3 | 158 | 5 |
| vol_box 0.5% / vol_gotobi 3% / fade 0.5% / m3 3% | 8 | 23 | 17 | 31 | 33 | 62 | 3.1 | 5.5 | 161 | 4 |
| vol_box 0.5% / vol_gotobi 3% / m3 4% | 6 | 23 | 8 | 36 | 12 | 73 | 3.0 | 7.4 | 137 | 0 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | 7 | 22 | 9 | 33 | 19 | 76 | 3.5 | 5.5 | 132 | 3 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% | 7 | 22 | 7 | 32 | 19 | 74 | 3.6 | 5.8 | 135 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 4% | 3 | 22 | 4 | 33 | 6 | 92 | 4.5 | 6.7 | 109 | 0 |
| vol_box 0.5% / vol_gotobi 4% / fade 0.5% / m3 4% | 10 | 21 | 33 | 25 | 52 | 43 | 2.0 | 5.9 | 235 | 23 |
| vol_box 0.5% / vol_gotobi 4.9% / m3 4% | 12 | 21 | 59 | 24 | 71 | 25 | 1.1 | 5.1 | 392 | 75 |
| vol_box 0.5% / vol_gotobi 4% / fade 0.5% / m3 3% | 10 | 21 | 32 | 25 | 53 | 41 | 1.9 | 6.3 | 242 | 22 |
| vol_box 0.5% / vol_gotobi 4.9% / m3 3% | 11 | 21 | 59 | 23 | 73 | 24 | 1.1 | 5.6 | 423 | 76 |
| vol_box 0.5% / vol_gotobi 2% / fade 0.5% / m3 4% | 6 | 21 | 14 | 33 | 30 | 67 | 3.0 | 5.4 | 150 | 2 |
| vol_box 0.5% / vol_gotobi 2% / fade 0.5% / m3 3% | 6 | 20 | 13 | 34 | 30 | 67 | 3.0 | 5.6 | 149 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | 3 | 20 | 4 | 32 | 5 | 92 | 4.7 | 7.2 | 109 | 0 |
| vol_box 0.25% / vol_gotobi 4.9% / m3 4% | 11 | 19 | 59 | 24 | 72 | 26 | 1.2 | 5.1 | 391 | 74 |
| vol_box 0.25% / vol_gotobi 4.9% / m3 3% | 11 | 18 | 59 | 23 | 72 | 25 | 1.2 | 5.2 | 395 | 75 |
| vol_box 0.25% / vol_gotobi 4.9% / fade 0.5% / m3 4% | 10 | 17 | 56 | 20 | 70 | 29 | 1.6 | 5.3 | 342 | 70 |
| vol_box 0.25% / vol_gotobi 4.9% / fade 0.5% / m3 3% | 10 | 17 | 54 | 20 | 71 | 28 | 1.5 | 5.6 | 354 | 69 |
| vol_box 0.5% / vol_gotobi 4.9% / fade 0.5% / m3 4% | 10 | 17 | 59 | 18 | 73 | 26 | 1.2 | 5.6 | 387 | 68 |
| vol_box 0.5% / vol_gotobi 4.9% / fade 0.5% / m3 3% | 10 | 17 | 58 | 18 | 73 | 25 | 1.2 | 6.1 | 401 | 68 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | 3 | 16 | 7 | 27 | 17 | 80 | 4.5 | 5.9 | 124 | 3 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 3% | 3 | 16 | 6 | 26 | 16 | 77 | 4.8 | 6.6 | 130 | 0 |
| vol_box 0.5% / vol_gotobi 2% / m3 3% | 4 | 15 | 6 | 31 | 11 | 72 | 3.4 | 8.2 | 139 | 0 |
| vol_box 0.5% / vol_gotobi 2% / m3 4% | 4 | 15 | 6 | 33 | 10 | 73 | 3.3 | 7.9 | 137 | 0 |
| vol_box 0.25% / vol_gotobi 2% / m3 3% | 1 | 9 | 2 | 24 | 3 | 94 | 4.9 | 7.8 | 106 | 0 |
| vol_box 0.25% / vol_gotobi 2% / m3 4% | 1 | 9 | 2 | 25 | 4 | 95 | 5.3 | 7.2 | 105 | 0 |

### Frontier: best pass <= 2m under a ruin ceiling (fail <= 2m), 2018 window, closed rule

| fail <=2m ceiling | best mix | pass <=2m % | fail <=2m % | pass eventually % | months per funded |
|---|---|---|---|---|---|
| 5% | vol_box 0.25% / vol_gotobi 3% / m3 4% | 21.5 | 4.2 | 91.6 | 6.7 |
| 10% | vol_box 0.25% / vol_gotobi 4% / m3 4% | 29.3 | 8.3 | 77.1 | 6.3 |
| 15% | vol_box 0.25% / vol_gotobi 4% / m3 4% | 29.3 | 8.3 | 77.1 | 6.3 |
| 25% | vol_box 0.25% / vol_gotobi 4% / m3 4% | 29.3 | 8.3 | 77.1 | 6.3 |

## Recommended static mix under the ruin ceiling: vol_box 0.25% / vol_gotobi 4% / m3 4%

| window | rule | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | months per funded | fail daily % |
|---|---|---|---|---|---|---|---|---|---|
| all | closed | 9 | 27 | 15 | 37 | 25 | 61 | 8.4 | 1 |
| all | floating | 9 | 25 | 26 | 34 | 42 | 50 | 6.5 | 31 |
| 2018 | closed | 7 | 29 | 8 | 41 | 16 | 77 | 6.3 | 0 |
| 2018 | floating | 7 | 28 | 16 | 38 | 27 | 64 | 6.3 | 19 |
| 2021 | closed | 8 | 35 | 11 | 51 | 21 | 74 | 4.4 | 0 |
| 2021 | floating | 8 | 33 | 19 | 47 | 34 | 61 | 4.7 | 19 |

Base mix for comparison: vol_box 0.25% / vol_gotobi 3% / m3 3%

| window | rule | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | months per funded | fail daily % |
|---|---|---|---|---|---|---|---|---|---|
| all | closed | 5 | 19 | 8 | 29 | 14 | 76 | 9.9 | 0 |
| all | floating | 5 | 19 | 16 | 28 | 27 | 64 | 10.1 | 16 |
| 2018 | closed | 3 | 20 | 4 | 32 | 5 | 92 | 7.2 | 0 |
| 2018 | floating | 3 | 20 | 7 | 30 | 16 | 79 | 7.9 | 12 |
| 2021 | closed | 4 | 25 | 5 | 40 | 7 | 89 | 5.0 | 0 |
| 2021 | floating | 4 | 25 | 10 | 38 | 22 | 73 | 5.6 | 17 |

## Family B: dynamic risk schemes (closed rule). boost = x1.5 in the first half of a phase target; p2half = half risk in phase 2; protect = half risk below 0.97 of the phase start; finish = x1.5 at or above 70% of the target

| mix | scheme | window | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | months per funded | fail daily % |
|---|---|---|---|---|---|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 3% / m3 3% | boost | 2018 | 10 | 25 | 33 | 31 | 50 | 39 | 7.5 | 54 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | boost+p2half | 2018 | 5 | 23 | 24 | 32 | 35 | 60 | 6.1 | 35 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | boost+protect | 2018 | 9 | 25 | 23 | 31 | 38 | 48 | 8.3 | 42 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | finish | 2018 | 3 | 21 | 5 | 32 | 6 | 91 | 7.3 | 2 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | p2half | 2018 | 1 | 12 | 2 | 23 | 3 | 95 | 8.3 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | protect | 2018 | 3 | 18 | 0 | 25 | 0 | 98 | 8.6 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | static | 2018 | 3 | 20 | 4 | 32 | 5 | 92 | 7.2 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | boost | all | 11 | 22 | 42 | 27 | 59 | 32 | 7.8 | 61 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | boost+p2half | all | 7 | 21 | 33 | 28 | 44 | 49 | 7.2 | 44 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | boost+protect | all | 10 | 22 | 34 | 28 | 49 | 38 | 9.0 | 54 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | finish | all | 4 | 19 | 11 | 27 | 20 | 69 | 10.6 | 6 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | p2half | all | 2 | 12 | 6 | 23 | 10 | 85 | 11.2 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | protect | all | 5 | 17 | 1 | 25 | 3 | 93 | 11.5 | 0 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | static | all | 5 | 19 | 8 | 29 | 14 | 76 | 9.9 | 0 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | boost | 2018 | 16 | 27 | 52 | 30 | 64 | 33 | 4.1 | 67 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | boost+p2half | 2018 | 8 | 25 | 41 | 31 | 48 | 51 | 4.5 | 46 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | boost+protect | 2018 | 15 | 22 | 51 | 25 | 65 | 30 | 5.5 | 68 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | finish | 2018 | 7 | 24 | 17 | 35 | 27 | 62 | 6.8 | 17 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | p2half | 2018 | 3 | 20 | 7 | 29 | 9 | 86 | 7.7 | 0 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | protect | 2018 | 7 | 26 | 3 | 36 | 3 | 89 | 7.6 | 0 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | static | 2018 | 7 | 29 | 8 | 41 | 16 | 77 | 6.3 | 0 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | boost | all | 15 | 23 | 58 | 25 | 70 | 27 | 4.6 | 73 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | boost+p2half | all | 9 | 22 | 47 | 26 | 55 | 42 | 5.4 | 53 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | boost+protect | all | 14 | 21 | 55 | 23 | 70 | 26 | 5.8 | 71 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | finish | all | 9 | 24 | 23 | 33 | 35 | 50 | 9.0 | 15 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | p2half | all | 4 | 18 | 13 | 27 | 18 | 74 | 10.2 | 1 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | protect | all | 9 | 24 | 6 | 33 | 11 | 73 | 11.0 | 2 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | static | all | 9 | 27 | 15 | 37 | 25 | 61 | 8.4 | 1 |

## Stress (pass <=2m % / fail <=2m % / pass eventually %)

| mix | window | closed | floating | +0.3 pip slippage | half edge |
|---|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 4% / m3 4% | 2018 | 29 / 8 / 77 | 28 / 16 / 64 | 28 / 9 / 72 | 17 / 22 / 38 |
| vol_box 0.25% / vol_gotobi 4% / m3 4% | all | 27 / 15 / 61 | 25 / 26 / 50 | 26 / 16 / 57 | 17 / 30 / 32 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | 2018 | 20 / 4 / 92 | 20 / 7 / 79 | 19 / 4 / 83 | 11 / 9 / 55 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | all | 19 / 8 / 76 | 19 / 16 / 64 | 18 / 9 / 68 | 12 / 15 / 41 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | 2018 | 22 / 7 / 74 | 22 / 12 / 70 | 21 / 9 / 65 | 17 / 18 / 40 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | all | 20 / 11 / 59 | 19 / 19 / 52 | 19 / 13 / 50 | 16 / 22 / 34 |

## Year-block bootstrap (1000 draws), 2018 window, closed rule: p10 / p50 / p90

| mix | pass <=2m % | fail <=2m % | pass eventually % | months per funded |
|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 4% / m3 4% | 17 / 29 / 38 | 3 / 8 / 12 | 70 / 78 / 83 | 4.6 / 6.4 / 8.7 |
| vol_box 0.25% / vol_gotobi 3% / m3 3% | 9 / 20 / 29 | 1 / 4 / 6 | 89 / 92 / 95 | 5.2 / 7.4 / 9.9 |
