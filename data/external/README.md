# External inputs (built 2026-10-14 by scripts/build_external.py)

Every table has `ts_avail` (UTC, naive): the first moment a row may be used. Strategies read these through `F.ext_asof` / `F.ext_rows` (see edge/engine/features.py); the leak tests cut and perturb them at the primary bar's close like auxiliary markets.

## calendar.parquet

71,033 rows, 2009-12-31 .. 2025-04-07. Columns: ts_release, ts_avail, time_known, time_source (scraped / typical / unknown), currency, event, impact (high / medium / low / none), actual, forecast, previous (strings as published), actual_num, forecast_num, previous_num (K/M/B/T scaled, % kept as the number), surprise = actual - forecast, surprise_z = surprise / std of that event's earlier surprises (at least 8), source.

Sources: 2010-2023 github.com/spoluan/forex-factory-scraper (datasets/forex_factory_calendar_YYYY.csv, ForexFactory scrape, times UTC+8 without daylight saving); 2024-01-01 .. 2025-04-07 huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar (forex_factory_cache.csv, MIT licence on the file, ForexFactory scrape). ForexFactory's own terms apply to the underlying data: private research use only. No source after 2025-04-07 yet.

- US Non-Farm Employment Change release times (UTC): {'12:30': 117, '13:30': 73} over 190 rows
- 2024+ NFP timestamps: ['2024-01-05 13:30', '2024-02-02 13:30', '2024-03-08 13:30', '2024-04-05 12:30', '2024-05-03 12:30', '2024-06-07 12:30']
- high-impact rows per year: {2010: 1163, 2011: 1191, 2012: 1159, 2013: 1159, 2014: 1207, 2015: 1189, 2016: 1096, 2017: 1010, 2018: 837, 2019: 839, 2020: 748, 2021: 545, 2022: 677, 2023: 908, 2024: 921, 2025: 250}
- time_source counts: {'scraped': 65586, 'unknown': 3578, 'typical': 1869}
- high-impact rows with numeric actual and forecast: 10304 of 14899; with surprise_z: 9311

## cot.parquet

9,345 rows, Tuesday positions 2010-01-05 .. 2026-10-06. Columns: market (EUR, JPY, GBP, CHF, CAD, AUD, NZD, USDX, SPX, NDX from the Traders in Financial Futures report; GOLD from the Disaggregated report), ts_asof, ts_release_date, ts_avail (15:30 New York on the release date), oi, and per group long / short / net / net_oi: spec (leveraged funds; managed money for gold), inst (asset managers; swap dealers for gold), comm (dealers; producers for gold), other, nonrept.

Source: cftc.gov/files/dea/history/fut_fin_txt_YYYY.zip and fut_disagg_txt_YYYY.zip, 2010-2026, public domain. Release dates: three US business days after the Tuesday (CFTC closures and holiday shifts from the gj-strat cot_positioning research); the 2013, 2018-19 and 2025 shutdown weeks and the 2023 ION-incident weeks are usable only from the end of their catch-up. gj-strat already tested positioning as a standalone signal (8 variants, negative); use it as a conditioning state.

- contracts: {'090741': 'CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE ', '092741': 'SWISS FRANC - CHICAGO MERCANTILE EXCHANGE ', '096742': 'BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE ', '097741': 'JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE ', '098662': 'U.S. DOLLAR INDEX - ICE FUTURES U.S. ', '099741': 'EURO FX - CHICAGO MERCANTILE EXCHANGE ', '112741': 'NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE ', '13874A': 'E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE ', '209742': 'NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE ', '232741': 'AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE ', '088691': 'GOLD - COMMODITY EXCHANGE INC. '}
- rows without an as-of date dropped: 0
- rows per market: {'GOLD': 875, 'AUD': 847, 'CAD': 847, 'CHF': 847, 'EUR': 847, 'GBP': 847, 'JPY': 847, 'NDX': 847, 'NZD': 847, 'SPX': 847, 'USDX': 847}
- as-of range: 2010-01-05 .. 2026-10-06; release lag days: {3: 8223, 4: 66, 6: 605, 7: 55, 10: 22, 14: 22, 17: 22, 21: 22, 24: 22, 28: 22, 31: 22, 35: 22, 38: 22, 42: 22, 45: 22, 49: 22, 52: 11, 56: 11, 59: 11, 63: 11, 71: 11, 77: 11, 80: 11, 84: 11, 91: 11, 98: 11, 105: 11, 112: 11}

## vol.parquet

Daily CBOE implied-volatility closes from FRED: vix (S&P 500), vxn (Nasdaq-100), evz (EuroCurrency ETF, i.e. EURUSD implied vol), gvz (gold), ovx (oil). Columns: ts_avail (21:30 UTC on the observation date), date, vix, vxn, evz, gvz, ovx.

Source: fred.stlouisfed.org/graph/fredgraph.csv?id=<series>, downloaded 2026-10-14. FRED terms: non-commercial use.

- range 2009-01-01 .. 2026-10-12, 4638 days; missing per series: {'vix': 134, 'vxn': 165, 'evz': 564, 'gvz': 165, 'ovx': 165}

## tfx.parquet

TFX (Tokyo Financial Exchange) Click 365 weekly retail long and short positions for 33 pairs, Tuesdays from
2022-11-22, usable from the Tuesday plus 8 days (ts_avail). Columns: pair, symbol, ts_asof, sell, buy, oi, net,
long_share, ts_avail. Built by scripts/build_external_tfx.py from the exchange's .xls files (data/external/tfx/raw);
details and caveats in data/external/tfx/README.md. Short history: usable for check-period and live conditioning,
not for design-period tests.

## tfx_daily.parquet

TFX Click 365 daily statistics per pair (36 pairs, trading days 2005-07-01 on): prev_settle, open, high, low, close, settle,
change, swap_point, volume, oi, d_oi, d_oi_pct, ret, with pair, symbol, date and ts_avail (= date + 1 day 00:00 UTC). Total
open interest only (no long/short split), so it is a direction-free retail-flow proxy with design-period history; tfx.parquet
holds the weekly long/short split from 2022-11. Built by scripts/build_external_tfx_daily.py; details in
data/external/tfx/README_daily.md.
