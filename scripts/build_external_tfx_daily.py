"""Build data/external/tfx_daily.parquet: daily Click 365 (Tokyo Financial Exchange) quotes, volume and total open
interest per currency pair, 2005-07-01 onward, from the TFX historical database.

Source: https://www.tfx.co.jp/historical/fx/result with HistoricalData[submit_type]=csv (the "CSV download" button of
the summary form at tfx.co.jp/historical/fx/). One request per calendar year returns every listed pair with the
previous settlement, open, high, low, close, settlement, change, swap point, trading volume and open interest for each
Click 365 trading day (Monday to Friday, Japanese holidays included). Raw files are cached under
data/external/tfx/raw/daily/fx_result_YYYY.csv (cp932); the current year is re-downloaded on every run.

Open interest here is the total (longs = shorts), no direction. The direction proxy is the change in open interest
read against the day's price move: Japanese retail adds to yen-cross longs when the pair falls and takes profit when
it rises, so a rise in open interest on a down day reads as dip-buying. d_oi, d_oi_pct and ret are provided for that;
the weekly long/short split (data/external/tfx.parquet, 2022-11 onward) is the direct measure for the holdout years.

Availability: the Click 365 trading day D ends at about 06:00 Tokyo on D+1 (05:00 during US daylight-saving time) and
TFX's daily report for D is generated minutes later (report header times 05:10 / 07:10 Tokyo). ts_avail = D + 1 day
00:00 UTC (09:00 Tokyo), which is after our D1 bar for D closes (17:00 New York).

    .venv/Scripts/python.exe -I scripts/build_external_tfx_daily.py            # use the cache, refresh the current year
    .venv/Scripts/python.exe -I scripts/build_external_tfx_daily.py --refetch  # re-download every year
"""
from __future__ import annotations

import io
import sys
import time
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
RAW = EXT / "tfx" / "raw" / "daily"
URL = "https://www.tfx.co.jp/historical/fx/result"
FIRST_YEAR = 2005          # Click 365 listed on 2005-07-01
PAUSE_S = 1.5

JPY = ["USD/JPY", "EUR/JPY", "GBP/JPY", "AUD/JPY", "CHF/JPY", "CAD/JPY", "NZD/JPY", "ZAR/JPY", "TRY/JPY", "NOK/JPY",
       "SEK/JPY", "HKD/JPY", "PLN/JPY", "MXN/JPY", "CNH/JPY", "HUF/JPY", "CZK/JPY"]
CROSS = ["EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/CAD", "GBP/CHF", "USD/CHF", "EUR/CHF", "EUR/AUD", "GBP/AUD", "EUR/GBP"]
LARGE = ["USL/JPY", "EUL/JPY", "GBL/JPY", "AUL/JPY", "EUL/USL"]
DELISTED = ["CNY/JPY", "KRW/JPY", "INR/JPY"]
FIELDS = ["settlement_price", "open", "high", "low", "last", "day_settlement_price", "day_before_ratio", "swap_point",
          "trading_volume", "open_interest"]
COLS = {"商品名": "pair", "商品タイプ": "name", "取引日": "date", "前日清算価格": "prev_settle", "始値": "open", "高値": "high",
        "安値": "low", "終値": "close", "当日清算価格": "settle", "前日比": "change", "スワップポイント": "swap_point",
        "取引数量": "volume", "建玉数量": "oi"}
# TFX pair code -> symbol in our price store
STORE = {"USD/JPY": "USDJPY", "EUR/JPY": "EURJPY", "GBP/JPY": "GBPJPY", "AUD/JPY": "AUDJPY", "CHF/JPY": "CHFJPY",
         "CAD/JPY": "CADJPY", "NZD/JPY": "NZDJPY", "EUR/USD": "EURUSD", "GBP/USD": "GBPUSD", "GBP/CHF": "GBPCHF",
         "USD/CHF": "USDCHF", "USD/CAD": "USDCAD", "AUD/USD": "AUDUSD", "EUR/CHF": "EURCHF", "EUR/GBP": "EURGBP",
         "NZD/USD": "NZDUSD", "EUR/AUD": "EURAUD", "GBP/AUD": "GBPAUD"}


def params(year: int, end: date) -> list[tuple[str, str]]:
    p = [("HistoricalData[submit_type]", "csv"),
         ("HistoricalData[period_start_type]", "date"),
         ("HistoricalData[period_start][year]", str(year)), ("HistoricalData[period_start][month]", "1"),
         ("HistoricalData[period_start][day]", "1"),
         ("HistoricalData[period_end_type]", "date"),
         ("HistoricalData[period_end][year]", str(end.year)), ("HistoricalData[period_end][month]", str(end.month)),
         ("HistoricalData[period_end][day]", str(end.day))]
    p += [("HistoricalData[product_type1][]", x) for x in JPY]
    p += [("HistoricalData[product_type2][]", x) for x in CROSS]
    p += [("HistoricalData[product_type3][]", x) for x in LARGE]
    p += [("HistoricalData[product_type4][]", x) for x in DELISTED]
    p += [("HistoricalData[get_preference][]", f) for f in FIELDS]
    return p


def fetch_year(client: httpx.Client, year: int) -> bytes:
    today = date.today()
    end = date(year, 12, 31) if year < today.year else today
    r = client.get(URL, params=params(year, end))
    r.raise_for_status()
    body = r.content
    if b"<html" in body[:400].lower() or "octet-stream" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"{year}: TFX returned a web page instead of the CSV (form or limits changed?)")
    return body


def download(refetch: bool) -> list[Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    today = date.today()
    paths = []
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True) as client:
        for year in range(FIRST_YEAR, today.year + 1):
            out = RAW / f"fx_result_{year}.csv"
            if out.exists() and not refetch and year < today.year:
                paths.append(out)
                continue
            out.write_bytes(fetch_year(client, year))
            print(f"fetched {year}: {out.stat().st_size:,} bytes", file=sys.stderr)
            paths.append(out)
            time.sleep(PAUSE_S)
    return paths


def parse_file(path: Path) -> pd.DataFrame:
    text = path.read_bytes().decode("cp932")
    lines = text.splitlines()
    if not lines[0].startswith("期間指定"):
        raise ValueError(f"{path.name}: unexpected first line {lines[0][:60]!r}")
    df = pd.read_csv(io.StringIO("\n".join(lines[2:])), dtype=str, na_values=["－－－", "---", ""], keep_default_na=False)
    df = df.rename(columns=COLS)
    missing = [c for c in COLS.values() if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}; got {list(df.columns)}")
    for c in ("prev_settle", "open", "high", "low", "close", "settle", "change", "swap_point", "volume", "oi"):
        df[c] = pd.to_numeric(df[c].str.replace(",", "", regex=False).str.strip(), errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="%Y/%m/%d")
    return df


def build(paths: list[Path]) -> pd.DataFrame:
    df = pd.concat([parse_file(p) for p in paths], ignore_index=True)
    df = df.drop_duplicates(subset=["pair", "date"], keep="last")
    # rows before a pair's listing (or after its delisting) carry no quotes and no open interest: drop them
    df = df[df["oi"].notna() & ((df["oi"] > 0) | df["volume"].fillna(0).gt(0))].copy()
    df = df.sort_values(["pair", "date"]).reset_index(drop=True)
    g = df.groupby("pair", sort=False)
    df["oi_prev"] = g["oi"].shift(1)
    df["d_oi"] = df["oi"] - df["oi_prev"]
    df["d_oi_pct"] = df["d_oi"] / df["oi_prev"].where(df["oi_prev"] > 0)
    df["ret"] = df["settle"] / df["prev_settle"].where(df["prev_settle"] > 0) - 1.0
    df["symbol"] = df["pair"].map(STORE)
    df["ts_avail"] = df["date"] + pd.Timedelta(days=1)
    df["volume"] = df["volume"].fillna(0).astype("int64")
    df["oi"] = df["oi"].astype("int64")
    out = df[["pair", "symbol", "date", "prev_settle", "open", "high", "low", "close", "settle", "change", "swap_point",
              "volume", "oi", "d_oi", "d_oi_pct", "ret", "ts_avail"]]
    return out.sort_values(["ts_avail", "pair"]).reset_index(drop=True)


def check(df: pd.DataFrame) -> list[str]:
    notes = []
    if df.duplicated(subset=["pair", "date"]).any():
        raise ValueError("duplicate pair/date rows")
    if (df["date"].dt.dayofweek > 4).any():
        raise ValueError("weekend trading days present")
    span = df.groupby("pair")["date"].agg(["min", "max", "count"])
    notes.append(f"{df['pair'].nunique()} pairs, {len(df):,} rows, trading days {df['date'].min().date()} .. {df['date'].max().date()}")
    first = span.sort_values("min")
    notes.append("listing (first row with open interest): " + ", ".join(f"{p} {r['min'].date()}" for p, r in first.iterrows()))
    gone = span[span["max"] < df["date"].max() - pd.Timedelta(days=10)]
    if len(gone):
        notes.append("no longer quoted: " + ", ".join(f"{p} (last {r['max'].date()})" for p, r in gone.iterrows()))
    usd = df[df["pair"] == "USD/JPY"].set_index("date")
    yrs = usd["oi"].groupby(usd.index.year).agg(["mean", "max"]).astype(int)
    notes.append("USD/JPY mean open interest by year: " + ", ".join(f"{y}: {int(r['mean']):,}" for y, r in yrs.iterrows()))
    # descriptive only: does open interest rise on down days? (Japanese retail dip-buying fingerprint)
    for pair in ("USD/JPY", "AUD/JPY", "EUR/USD"):
        x = df[df["pair"] == pair].dropna(subset=["ret", "d_oi_pct"])
        pre = x[x["date"] < "2024-01-01"]
        if len(pre) > 500:
            c = float(np.corrcoef(pre["ret"], pre["d_oi_pct"])[0, 1])
            down = pre.loc[pre["ret"] < 0, "d_oi_pct"].mean() * 1e4
            up = pre.loc[pre["ret"] > 0, "d_oi_pct"].mean() * 1e4
            notes.append(f"{pair} 2005-2023: corr(daily return, open-interest change) {c:+.2f}; mean OI change on down days "
                         f"{down:+.1f} bp, on up days {up:+.1f} bp (descriptive, pre-holdout only)")
    mapped = df["symbol"].notna().sum()
    notes.append(f"{mapped:,} rows map to a price-store symbol ({df.loc[df['symbol'].notna(), 'pair'].nunique()} pairs)")
    return notes


def readme(df: pd.DataFrame, notes: list[str], n_files: int) -> str:
    lines = [f"# tfx_daily.parquet (built {date.today().isoformat()} by scripts/build_external_tfx_daily.py from {n_files} yearly CSVs)", "",
             f"{len(df):,} rows: one per Click 365 pair per trading day. Columns: pair (TFX code), symbol (price-store symbol or "
             "null), date (Click 365 trading day; it ends about 06:00 Tokyo the next morning, so it matches our New York-close "
             "D1 bar), prev_settle, open, high, low, close, settle, change, swap_point (yen per contract per day, long side), "
             "volume (contracts, one side), oi (total open contracts at the close), d_oi, d_oi_pct (change in oi versus the "
             "previous trading day), ret (settle / prev_settle - 1), ts_avail (= date + 1 day 00:00 UTC).", "",
             f"Source: {URL} (HistoricalData[submit_type]=csv, one request per year, cached in data/external/tfx/raw/daily/). "
             "Open interest has no direction: the retail-flow proxy is d_oi read against ret (open interest rising on a down day "
             "= dip-buying by the structurally long Japanese retail book). The weekly long/short split in tfx.parquet "
             "(2022-11 onward) is the direct measure. Rows before a pair's listing (no quotes, zero open interest) are dropped.", ""]
    lines += [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> None:
    paths = download(refetch="--refetch" in argv)
    df = build(paths)
    notes = check(df)
    df.to_parquet(EXT / "tfx_daily.parquet", index=False)
    text = readme(df, notes, len(paths))
    (EXT / "tfx" / "README_daily.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
