# USDJPY basket sizing for Alpha Swing $10k

Rules: Alpha Capital Group Alpha Swing; daily loss on the closed balance (floating = stress case); day resets at 17:00 New York; challenge starts up to 2025-10-07. Goal: {'pass_eventually_min_pct': 60.0, 'pass_le_3m_min_pct': 25.0, 'fail_le_6m_max_pct': 35.0, 'months_per_funded_account_max': 6.0, 'window': '2018'}

## Step 0: replication of the gj-strat incumbent (vol-box 0.25 / vol-gotobi 3 / fade 0.5 / M-3 3)

| window | pass eventually % (gj-strat) | months per funded (gj-strat) | pass <=3m % | fail <=6m % | fail daily % |
|---|---|---|---|---|---|
| all | 59.1 (59.1) | 7.3 (7.3) | 27.6 | 30.9 | 2.7 |
| 2018 | 74.0 (74.0) | 5.8 (5.8) | 32.3 | 19.2 | 0.0 |

## Step 1: grid of 224 mixes; 4 meet the goal on the 2018 window and the safety floor on all starts

| mix | pass eventually % (2018 / all) | months per funded (2018 / all) | pass <=3m % | fail <=6m % (2018 / all) | fail daily % |
|---|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | 75.5 / 59.1 | 5.5 / 6.9 | 33.4 | 18.8 / 31.3 | 2.6 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% | 74.0 / 59.1 | 5.8 / 7.3 | 32.3 | 19.2 / 30.9 | 0.0 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | 80.5 / 66.6 | 5.9 / 7.1 | 27.1 | 16.7 / 25.7 | 3.4 |
| vol_gotobi 3% / fade 0.5% / m3 4% | 70.0 / 56.3 | 6.0 / 8.3 | 27.0 | 21.4 / 29.6 | 3.4 |
| incumbent: vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% | 74.0 / 59.1 | 5.8 / 7.3 | 32.3 | 19.2 / 30.9 | 0.0 |

Fastest mixes that fail the goal (for reference):

| vol_box 0.5% / vol_gotobi 4% / fade 1% / m3 4% | 41.8 / 37.9 | 3.7 / 4.1 | 32.0 | 57.6 / 61.2 | 19.8 |
| vol_box 0.5% / vol_gotobi 3% / fade 1% / m3 4% | 46.3 / 40.7 | 4.0 / 4.4 | 35.7 | 52.0 / 58.1 | 7.4 |
| vol_box 0.25% / vol_gotobi 4% / fade 1% / m3 4% | 45.2 / 40.3 | 4.0 / 4.2 | 32.8 | 53.4 / 58.5 | 18.0 |
| vol_gotobi 4% / fade 1% / m3 4% | 46.5 / 39.3 | 4.1 / 4.7 | 33.2 | 53.3 / 60.2 | 17.6 |
| vol_box 0.5% / vol_gotobi 4% / fade 1% / m3 3% | 39.6 / 36.9 | 4.3 / 4.4 | 31.4 | 57.3 / 61.0 | 20.0 |

## Step 2: stress on the top 5 and the incumbent (pass eventually % / months per funded / fail <=6m %)

| mix | window | closed | floating | +0.3 pip slippage | half edge |
|---|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | all | 59 / 6.9 / 31 | 52 / 6.8 / 40 | 53 / 7.6 / 37 | 38 / 9.9 / 51 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | 2018 | 76 / 5.5 / 19 | 71 / 5.6 / 24 | 69 / 5.9 / 25 | 48 / 8.4 / 41 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | 2021 | 77 / 3.8 / 20 | 71 / 4.0 / 27 | 70 / 4.2 / 27 | 52 / 6.0 / 43 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | all | 59 / 7.3 / 31 | 52 / 7.2 / 39 | 50 / 8.3 / 38 | 34 / 11.6 / 51 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | 2018 | 74 / 5.8 / 19 | 70 / 5.9 / 24 | 65 / 6.3 / 28 | 40 / 10.7 / 42 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | 2021 | 78 / 4.0 / 19 | 72 / 4.1 / 26 | 69 / 4.5 / 28 | 47 / 7.0 / 45 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | all | 67 / 7.1 / 26 | 60 / 7.2 / 33 | 61 / 7.8 / 28 | 39 / 11.4 / 44 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | 2018 | 80 / 5.9 / 17 | 79 / 5.9 / 18 | 75 / 6.4 / 18 | 51 / 9.4 / 34 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | 2021 | 80 / 4.2 / 19 | 78 / 4.2 / 21 | 78 / 4.5 / 20 | 58 / 6.5 / 35 |
| vol_gotobi 3% / fade 0.5% / m3 4% | all | 56 / 8.3 / 30 | 48 / 8.8 / 39 | 51 / 8.9 / 34 | 40 / 11.0 / 46 |
| vol_gotobi 3% / fade 0.5% / m3 4% | 2018 | 70 / 6.0 / 21 | 62 / 6.4 / 29 | 66 / 6.5 / 25 | 53 / 9.0 / 36 |
| vol_gotobi 3% / fade 0.5% / m3 4% | 2021 | 70 / 4.6 / 25 | 58 / 5.1 / 37 | 66 / 5.0 / 29 | 51 / 6.9 / 43 |

## Step 3: year-block bootstrap (1000 draws), closed-balance rule

| mix | window | pass eventually % p10 / p50 / p90 | months per funded p10 / p50 / p90 | pass <=3m % p10 / p50 / p90 | fail <=6m % p10 / p50 / p90 |
|---|---|---|---|---|---|
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | all | 51 / 59 / 67 | 5.7 / 6.9 / 8.7 | 21 / 28 / 35 | 25 / 31 / 37 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | 2018 | 68 / 76 / 82 | 4.3 / 5.5 / 6.9 | 22 / 33 / 44 | 14 / 19 / 23 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | all | 51 / 59 / 67 | 6.0 / 7.3 / 9.1 | 20 / 28 / 35 | 25 / 31 / 37 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% (incumbent) | 2018 | 66 / 75 / 81 | 4.5 / 5.9 / 7.5 | 21 / 32 / 42 | 15 / 19 / 23 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | all | 60 / 67 / 73 | 6.0 / 7.1 / 8.5 | 17 / 25 / 31 | 21 / 26 / 31 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | 2018 | 75 / 80 / 86 | 4.7 / 5.9 / 7.2 | 17 / 27 / 36 | 12 / 17 / 21 |
| vol_gotobi 3% / fade 0.5% / m3 4% | all | 48 / 56 / 65 | 6.7 / 8.2 / 10.4 | 18 / 24 / 29 | 24 / 30 / 35 |
| vol_gotobi 3% / fade 0.5% / m3 4% | 2018 | 62 / 71 / 79 | 4.8 / 5.9 / 7.3 | 19 / 27 / 35 | 15 / 21 / 27 |

## Drop-one from the best candidate (vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4%), 2018 window, closed rule

| without | pass eventually % | months per funded | pass <=3m % | fail <=6m % |
|---|---|---|---|---|
| vol_box | 70.0 | 6.0 | 27.0 | 21.4 |
| vol_gotobi | 74.1 | 8.6 | 12.9 | 18.5 |
| fade | 91.6 | 6.7 | 33.2 | 6.0 |
| m3 | 64.2 | 7.5 | 29.8 | 22.2 |

## Floating (mark-to-market) daily rule, 2018 window, candidates

| mix | pass eventually % | months per funded | fail daily % |
|---|---|---|---|
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 4% | 71.0 | 5.6 | 5.0 |
| vol_box 0.25% / vol_gotobi 3% / fade 0.5% / m3 3% | 69.8 | 5.9 | 4.8 |
| vol_box 0.25% / vol_gotobi 2% / fade 0.5% / m3 4% | 79.2 | 5.9 | 1.5 |
| vol_gotobi 3% / fade 0.5% / m3 4% | 62.4 | 6.4 | 7.6 |

## Single live account

The goal metric (months per funded account) assumes failed challenges are restarted at once, so it rewards speed and tolerates blow-ups. The user holds one live account, where the chance of passing and the chance of losing the account matter more. Risk per leg in the mix names is vol-box / vol-gotobi / fade / M-3 in percent of balance.

### closed-balance daily rule (the stated rule)

| mix | window | pass <=3m % | pass <=6m % | pass <=12m % | fail <=6m % | pass eventually % | months per funded | fail daily % | fail max %|
|---|---|---|---|---|---|---|---|---|---|
| incumbent 0.25/3/0.5/3 | all | 28 | 44 | 55 | 31 | 59 | 7.3 | 3 | 38 |
| incumbent 0.25/3/0.5/3 | 2018 | 32 | 58 | 71 | 19 | 74 | 5.8 | 0 | 26 |
| incumbent 0.25/3/0.5/3 | 2021 | 43 | 73 | 78 | 19 | 78 | 4.0 | 0 | 22 |
| m3 4%: 0.25/3/0.5/4 | all | 28 | 46 | 57 | 31 | 59 | 6.9 | 4 | 37 |
| m3 4%: 0.25/3/0.5/4 | 2018 | 33 | 60 | 75 | 19 | 76 | 5.5 | 3 | 22 |
| m3 4%: 0.25/3/0.5/4 | 2021 | 44 | 73 | 77 | 20 | 77 | 3.8 | 4 | 19 |
| fade 0.25: 0.25/3/0.25/3 | all | 25 | 37 | 51 | 22 | 62 | 10.2 | 0 | 38 |
| fade 0.25: 0.25/3/0.25/3 | 2018 | 29 | 48 | 68 | 13 | 77 | 7.7 | 0 | 23 |
| fade 0.25: 0.25/3/0.25/3 | 2021 | 37 | 61 | 79 | 14 | 80 | 5.3 | 0 | 20 |
| no fade: 0.25/3/0/3 | all | 29 | 44 | 60 | 14 | 76 | 9.9 | 0 | 24 |
| no fade: 0.25/3/0/3 | 2018 | 32 | 52 | 73 | 5 | 92 | 7.2 | 0 | 8 |
| no fade: 0.25/3/0/3 | 2021 | 40 | 65 | 89 | 7 | 89 | 5.0 | 0 | 11 |
| no fade, m3 4%: 0.25/3/0/4 | all | 31 | 46 | 63 | 14 | 76 | 9.0 | 0 | 24 |
| no fade, m3 4%: 0.25/3/0/4 | 2018 | 33 | 53 | 77 | 6 | 92 | 6.7 | 0 | 8 |
| no fade, m3 4%: 0.25/3/0/4 | 2021 | 42 | 65 | 88 | 8 | 88 | 5.0 | 0 | 12 |
| no fade, gotobi 2%: 0.25/2/0/3 | all | 24 | 45 | 60 | 6 | 88 | 10.3 | 0 | 12 |
| no fade, gotobi 2%: 0.25/2/0/3 | 2018 | 24 | 49 | 68 | 3 | 94 | 7.8 | 0 | 6 |
| no fade, gotobi 2%: 0.25/2/0/3 | 2021 | 30 | 61 | 82 | 4 | 91 | 5.4 | 0 | 8 |
| no fade, gotobi 4%: 0.25/4/0/4 | all | 37 | 47 | 56 | 25 | 61 | 8.4 | 1 | 38 |
| no fade, gotobi 4%: 0.25/4/0/4 | 2018 | 41 | 55 | 70 | 16 | 77 | 6.3 | 0 | 23 |
| no fade, gotobi 4%: 0.25/4/0/4 | 2021 | 51 | 64 | 74 | 21 | 74 | 4.4 | 0 | 26 |
| box 0.5, no fade: 0.5/3/0/3 | all | 31 | 42 | 52 | 29 | 56 | 9.0 | 3 | 41 |
| box 0.5, no fade: 0.5/3/0/3 | 2018 | 34 | 51 | 66 | 15 | 71 | 7.5 | 0 | 29 |
| box 0.5, no fade: 0.5/3/0/3 | 2021 | 43 | 62 | 78 | 14 | 78 | 5.4 | 0 | 22 |
| no box, no fade: 0/3/0/3 | all | 23 | 39 | 57 | 14 | 74 | 11.5 | 0 | 26 |
| no box, no fade: 0/3/0/3 | 2018 | 23 | 42 | 68 | 8 | 81 | 8.9 | 0 | 19 |
| no box, no fade: 0/3/0/3 | 2021 | 30 | 53 | 70 | 12 | 74 | 7.5 | 0 | 26 |

### daily loss marked to market

| mix | window | pass <=3m % | pass <=6m % | pass <=12m % | fail <=6m % | pass eventually % | months per funded | fail daily % | fail max %|
|---|---|---|---|---|---|---|---|---|---|
| incumbent 0.25/3/0.5/3 | all | 25 | 41 | 50 | 39 | 52 | 7.2 | 16 | 32 |
| incumbent 0.25/3/0.5/3 | 2018 | 30 | 54 | 67 | 24 | 70 | 5.9 | 5 | 25 |
| incumbent 0.25/3/0.5/3 | 2021 | 40 | 67 | 72 | 26 | 72 | 4.1 | 7 | 21 |
| m3 4%: 0.25/3/0.5/4 | all | 26 | 42 | 52 | 40 | 52 | 6.8 | 20 | 28 |
| m3 4%: 0.25/3/0.5/4 | 2018 | 31 | 56 | 70 | 24 | 71 | 5.6 | 5 | 24 |
| m3 4%: 0.25/3/0.5/4 | 2021 | 41 | 67 | 71 | 27 | 71 | 4.0 | 8 | 22 |
| fade 0.25: 0.25/3/0.25/3 | all | 23 | 33 | 46 | 32 | 54 | 9.8 | 17 | 29 |
| fade 0.25: 0.25/3/0.25/3 | 2018 | 27 | 42 | 60 | 20 | 69 | 8.2 | 10 | 21 |
| fade 0.25: 0.25/3/0.25/3 | 2021 | 35 | 52 | 68 | 25 | 69 | 5.7 | 15 | 16 |
| no fade: 0.25/3/0/3 | all | 28 | 39 | 50 | 27 | 64 | 10.1 | 16 | 20 |
| no fade: 0.25/3/0/3 | 2018 | 30 | 45 | 62 | 16 | 79 | 7.9 | 12 | 9 |
| no fade: 0.25/3/0/3 | 2021 | 38 | 54 | 73 | 22 | 73 | 5.6 | 17 | 10 |
| no fade, m3 4%: 0.25/3/0/4 | all | 29 | 41 | 53 | 32 | 61 | 7.7 | 22 | 17 |
| no fade, m3 4%: 0.25/3/0/4 | 2018 | 31 | 46 | 65 | 17 | 78 | 7.4 | 14 | 8 |
| no fade, m3 4%: 0.25/3/0/4 | 2021 | 39 | 54 | 70 | 24 | 70 | 5.6 | 19 | 11 |
| no fade, gotobi 2%: 0.25/2/0/3 | all | 24 | 44 | 54 | 12 | 76 | 10.9 | 13 | 11 |
| no fade, gotobi 2%: 0.25/2/0/3 | 2018 | 24 | 49 | 64 | 7 | 89 | 8.0 | 7 | 4 |
| no fade, gotobi 2%: 0.25/2/0/3 | 2021 | 30 | 60 | 76 | 10 | 84 | 5.5 | 9 | 5 |
| no fade, gotobi 4%: 0.25/4/0/4 | all | 34 | 41 | 48 | 42 | 50 | 6.5 | 31 | 20 |
| no fade, gotobi 4%: 0.25/4/0/4 | 2018 | 38 | 47 | 61 | 27 | 64 | 6.3 | 19 | 17 |
| no fade, gotobi 4%: 0.25/4/0/4 | 2021 | 47 | 54 | 61 | 34 | 61 | 4.7 | 19 | 21 |
| box 0.5, no fade: 0.5/3/0/3 | all | 28 | 37 | 44 | 40 | 45 | 9.5 | 17 | 38 |
| box 0.5, no fade: 0.5/3/0/3 | 2018 | 30 | 44 | 56 | 25 | 58 | 8.5 | 10 | 33 |
| box 0.5, no fade: 0.5/3/0/3 | 2021 | 38 | 52 | 64 | 27 | 64 | 6.1 | 13 | 23 |
| no box, no fade: 0/3/0/3 | all | 22 | 34 | 49 | 25 | 61 | 12.0 | 19 | 19 |
| no box, no fade: 0/3/0/3 | 2018 | 23 | 39 | 58 | 20 | 66 | 9.4 | 19 | 15 |
| no box, no fade: 0/3/0/3 | 2021 | 29 | 48 | 56 | 29 | 56 | 8.0 | 27 | 17 |

### half of every leg's edge removed

| mix | window | pass <=3m % | pass <=6m % | pass <=12m % | fail <=6m % | pass eventually % | months per funded | fail daily % | fail max %|
|---|---|---|---|---|---|---|---|---|---|
| incumbent 0.25/3/0.5/3 | all | 21 | 27 | 33 | 51 | 34 | 11.6 | 4 | 63 |
| incumbent 0.25/3/0.5/3 | 2018 | 23 | 32 | 40 | 42 | 40 | 10.7 | 0 | 60 |
| incumbent 0.25/3/0.5/3 | 2021 | 31 | 39 | 47 | 45 | 47 | 7.0 | 0 | 53 |
| m3 4%: 0.25/3/0.5/4 | all | 22 | 30 | 37 | 51 | 38 | 9.9 | 6 | 57 |
| m3 4%: 0.25/3/0.5/4 | 2018 | 24 | 37 | 47 | 41 | 48 | 8.4 | 2 | 50 |
| m3 4%: 0.25/3/0.5/4 | 2021 | 32 | 44 | 52 | 43 | 52 | 6.0 | 3 | 45 |
| fade 0.25: 0.25/3/0.25/3 | all | 18 | 25 | 32 | 40 | 35 | 16.0 | 0 | 65 |
| fade 0.25: 0.25/3/0.25/3 | 2018 | 19 | 31 | 42 | 34 | 46 | 12.5 | 0 | 54 |
| fade 0.25: 0.25/3/0.25/3 | 2021 | 25 | 39 | 49 | 38 | 50 | 8.7 | 0 | 50 |
| no fade: 0.25/3/0/3 | all | 20 | 30 | 37 | 33 | 41 | 14.9 | 0 | 59 |
| no fade: 0.25/3/0/3 | 2018 | 20 | 36 | 47 | 24 | 55 | 12.7 | 0 | 45 |
| no fade: 0.25/3/0/3 | 2021 | 25 | 42 | 53 | 30 | 54 | 9.9 | 0 | 46 |
| no fade, m3 4%: 0.25/3/0/4 | all | 20 | 32 | 38 | 32 | 41 | 14.6 | 0 | 59 |
| no fade, m3 4%: 0.25/3/0/4 | 2018 | 21 | 39 | 50 | 21 | 55 | 12.7 | 0 | 45 |
| no fade, m3 4%: 0.25/3/0/4 | 2021 | 26 | 47 | 57 | 27 | 57 | 8.9 | 0 | 43 |
| no fade, gotobi 2%: 0.25/2/0/3 | all | 15 | 30 | 45 | 16 | 57 | 15.7 | 0 | 43 |
| no fade, gotobi 2%: 0.25/2/0/3 | 2018 | 13 | 31 | 56 | 6 | 71 | 13.9 | 0 | 29 |
| no fade, gotobi 2%: 0.25/2/0/3 | 2021 | 16 | 39 | 67 | 8 | 71 | 11.0 | 0 | 29 |
| no fade, gotobi 4%: 0.25/4/0/4 | all | 23 | 27 | 31 | 52 | 32 | 11.9 | 17 | 51 |
| no fade, gotobi 4%: 0.25/4/0/4 | 2018 | 23 | 29 | 37 | 43 | 38 | 12.2 | 11 | 51 |
| no fade, gotobi 4%: 0.25/4/0/4 | 2021 | 27 | 33 | 38 | 49 | 38 | 9.2 | 16 | 46 |
| box 0.5, no fade: 0.5/3/0/3 | all | 20 | 26 | 29 | 52 | 29 | 13.4 | 3 | 68 |
| box 0.5, no fade: 0.5/3/0/3 | 2018 | 21 | 30 | 36 | 44 | 36 | 12.1 | 0 | 64 |
| box 0.5, no fade: 0.5/3/0/3 | 2021 | 25 | 34 | 40 | 47 | 40 | 9.4 | 0 | 60 |
| no box, no fade: 0/3/0/3 | all | 15 | 26 | 34 | 26 | 42 | 19.4 | 0 | 58 |
| no box, no fade: 0/3/0/3 | 2018 | 16 | 29 | 44 | 21 | 55 | 14.3 | 0 | 45 |
| no box, no fade: 0/3/0/3 | 2021 | 21 | 39 | 48 | 28 | 50 | 12.0 | 0 | 50 |

### Recommendation

- For the live account, drop the fade leg: vol-box 0.25% + vol-gotobi 3% + M-3 3%. On 2018-2025 starts it passes eventually 92% of the time against 74% for the incumbent, loses the account within six months 5% of the time against 19%, with the same three-month pass odds (32% vs 32%). The price is time: median 4.7 months to pass instead of 3.6, and 7.2 months per funded account instead of 5.8, which misses the goal.yaml speed target of 6.0.
- M-3 at 4% instead of 3% is slightly faster (6.7 months per funded, 33% within three months) at the same safety, but M-3 made only +0.022 R per trade in 2024-2026 (33 trades), so 3% keeps less weight on the weakest recent leg.
- Why the fade hurts: it adds the most trades (1,672 at 0.5%, 24% winners, worst excursion 1.07 R on average) and most of the max-loss breaches. Without it the account fails by the 10% static loss in 8% of 2018+ starts instead of 26%; with the daily rule marked to market the no-fade mix still passes 79% against 70%, and with half the historical edge 55% against 40%.
- The safest mix measured is vol-gotobi at 2% with no fade (94% pass eventually, 3% ruin within six months on 2018+ starts; 88% / 12% on all starts), but it halves the chance of passing within three months (24%). Choose it only if time does not matter.
- The year-block bootstrap for the recommended mix on 2018+ starts: pass eventually 89-95% (10th-90th percentile), ruin within six months 3-7%, pass within three months 17-46%. All of this is backtest arithmetic on 2010-2025 trades with full costs; live slippage above 0.3 pips on the box would lower every number (see the slippage stress above).
- If the single-account view is the objective, goal.yaml should carry a ruin ceiling (fail <= 6m, say 10%) and a pass-eventually floor near 85% instead of ranking by months per funded account; that is the user's call, nothing in config was changed.
