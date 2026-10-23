# tfx.parquet (built 2026-10-14 by scripts/build_external_tfx.py from weekly_sellbuy_2026-10-13.xls)

6,699 rows: Japanese retail FX positions on the Tokyo Financial Exchange (Click 365), one row per pair per Tuesday. Columns: pair (TFX code, e.g. USD/JPY; USL/JPY etc. are the LARGE contracts), symbol (our price-store symbol or null), ts_asof (Tuesday, position at the close of that trading day), sell and buy (customers' open short and long contracts), oi = sell + buy, net = buy - sell, long_share = buy / oi, ts_avail (= ts_asof + 8 days 00:00 UTC; the file is republished on the following Tuesday, hour unverified).

Source: https://www.click365.jp/resorces/doc/weekly_sellbuy.xls (TFX, 為替売買動向, weekly). Contract sizes differ by pair, so compare long_share and net within a pair only. This is the only long/short split TFX publishes; its daily reports and 2010-2021 monthly statistics carry total open interest only. Click 365 is a minority of Japanese retail FX (the OTC brokers are larger) and the only venue that publishes positions, so treat it as a proxy for the retail yen-cross book.

- 203 Tuesdays 2022-11-22 .. 2026-10-06; gap days: {7.0: 202}
- 33 pairs; 18 of them map to a price-store symbol (3,654 rows)
- largest books on the last Tuesday (pair: oi, long_share): TRY/JPY: 1,806,819, 0.99, USD/JPY: 488,928, 0.31, MXN/JPY: 132,548, 0.87, GBP/JPY: 118,706, 0.29, ZAR/JPY: 80,476, 0.84
- USD/JPY long_share: min 0.19, median 0.26, max 0.37 (customers net short USD/JPY on every Tuesday of the history)
