"""Build data/external/tfx.parquet: Japanese retail FX positioning from the Tokyo Financial Exchange (Click 365).

Source: https://www.click365.jp/resorces/doc/weekly_sellbuy.xls ("為替売買動向", FX buy/sell trends). One row per
Tuesday: customers' open short (売り) and long (買い) contracts per currency pair at the close of the Tuesday trading
day (the Click 365 trading day ends 06:00 Tokyo the next morning), all 33 listed pairs, 2022-11-22 onward, no gaps.
Units are TFX contracts (trading units differ by pair: 10,000 currency units for the majors, more for ZAR, HKD,
MXN, HUF, CZK); compare long_share and net within a pair, not sizes across pairs.

Publication: the page says "updated every Tuesday"; on 2026-10-13 (Tuesday) the file carried rows up to 2026-10-06
and the HTTP Last-Modified header read 2026-10-13. So the row for Tuesday T appears on Tuesday T+7, at an unknown
hour. ts_avail = T + 8 days 00:00 UTC (Wednesday 09:00 Tokyo) is deliberately one day later than that; verify the
exact hour before trusting a shorter lag.

The daily TFX reports (tfx.co.jp/kawase/document/PRT-010-CSV-003-YYYYMMDD.CSV, 2010-) and the monthly statistics
PDFs (2010-2021) carry only total open interest per pair, no long/short split; this weekly file is the only split.

    .venv/Scripts/python.exe -I scripts/build_external_tfx.py            # parse the newest raw file
    .venv/Scripts/python.exe -I scripts/build_external_tfx.py --fetch    # download the current file first
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
RAW = EXT / "tfx" / "raw"
URL = "https://www.click365.jp/resorces/doc/weekly_sellbuy.xls"
LAG_DAYS = 8          # as-of Tuesday T -> usable from T+8 00:00 UTC (see module docstring)

# TFX pair code -> symbol in our price store (pairs missing here have no price series: LARGE contracts and exotics)
STORE = {"USD/JPY": "USDJPY", "EUR/JPY": "EURJPY", "GBP/JPY": "GBPJPY", "AUD/JPY": "AUDJPY", "CHF/JPY": "CHFJPY",
         "CAD/JPY": "CADJPY", "NZD/JPY": "NZDJPY", "EUR/USD": "EURUSD", "GBP/USD": "GBPUSD", "GBP/CHF": "GBPCHF",
         "USD/CHF": "USDCHF", "USD/CAD": "USDCAD", "AUD/USD": "AUDUSD", "EUR/CHF": "EURCHF", "EUR/GBP": "EURGBP",
         "NZD/USD": "NZDUSD", "EUR/AUD": "EURAUD", "GBP/AUD": "GBPAUD"}


def fetch() -> Path:
    import httpx
    out = RAW / f"weekly_sellbuy_{date.today().isoformat()}.xls"
    r = httpx.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60, follow_redirects=True)
    r.raise_for_status()
    if not r.content.startswith(b"\xd0\xcf\x11\xe0"):
        raise RuntimeError("download is not an .xls file (TFX may have changed the page)")
    RAW.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out


def newest_raw() -> Path:
    files = sorted(RAW.glob("weekly_sellbuy_*.xls"))
    if not files:
        raise FileNotFoundError(f"no raw file in {RAW}; run with --fetch")
    return files[-1]


def parse(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None, engine="xlrd")
    pairs = raw.iloc[0]
    sides = raw.iloc[2].astype(str).str.strip().str.lower()
    recs = []
    for c in range(1, raw.shape[1], 2):
        pair = str(pairs.iloc[c]).strip()
        if "/" not in pair:
            continue
        s_lab, b_lab = sides.iloc[c], sides.iloc[c + 1]
        if s_lab not in ("sell", "short") or b_lab not in ("buy", "long"):
            raise ValueError(f"unexpected column labels for {pair}: {s_lab}, {b_lab}")
        block = raw.iloc[3:, [0, c, c + 1]].copy()
        block.columns = ["asof", "sell", "buy"]
        block["pair"] = pair
        recs.append(block)
    df = pd.concat(recs, ignore_index=True)
    df["ts_asof"] = pd.to_datetime(df["asof"].astype(str).str.strip(), format="%m/%d/%Y", errors="coerce")
    df = df.dropna(subset=["ts_asof"]).drop(columns="asof")
    for col in ("sell", "buy"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
    df["oi"] = df["sell"] + df["buy"]
    df["net"] = df["buy"] - df["sell"]
    df["long_share"] = (df["buy"] / df["oi"].where(df["oi"] > 0)).astype("float64")
    df["symbol"] = df["pair"].map(STORE)
    df["ts_avail"] = df["ts_asof"] + pd.Timedelta(days=LAG_DAYS)
    df = df.sort_values(["ts_avail", "pair"]).reset_index(drop=True)
    return df[["pair", "symbol", "ts_asof", "sell", "buy", "oi", "net", "long_share", "ts_avail"]]


def check(df: pd.DataFrame) -> list[str]:
    dates = df["ts_asof"].drop_duplicates().sort_values()
    bad_dow = dates[dates.dt.dayofweek != 1]
    if len(bad_dow):
        raise ValueError(f"as-of dates that are not Tuesdays: {list(bad_dow.dt.date)[:5]}")
    gaps = dates.diff().dt.days.dropna().value_counts().to_dict()
    notes = [f"{len(dates)} Tuesdays {dates.min().date()} .. {dates.max().date()}; gap days: {gaps}"]
    per_pair = df.groupby("pair").size()
    if per_pair.nunique() != 1:
        raise ValueError(f"uneven rows per pair: {per_pair.to_dict()}")
    if (df[["sell", "buy"]] < 0).any().any():
        raise ValueError("negative position counts")
    mapped = df[df["symbol"].notna()]
    notes.append(f"{per_pair.index.size} pairs; {mapped['pair'].nunique()} of them map to a price-store symbol ({len(mapped):,} rows)")
    latest = df[df["ts_asof"] == dates.max()].set_index("pair")
    big = latest.sort_values("oi", ascending=False).head(5)
    notes.append("largest books on the last Tuesday (pair: oi, long_share): " +
                 ", ".join(f"{p}: {int(r.oi):,}, {r.long_share:.2f}" for p, r in big.iterrows()))
    usd = df[df["pair"] == "USD/JPY"]["long_share"]
    tail = " (customers net short USD/JPY on every Tuesday of the history)" if usd.max() < 0.5 else ""
    notes.append(f"USD/JPY long_share: min {usd.min():.2f}, median {usd.median():.2f}, max {usd.max():.2f}{tail}")
    return notes


def readme(src: Path, df: pd.DataFrame, notes: list[str]) -> str:
    lines = [f"# tfx.parquet (built {date.today().isoformat()} by scripts/build_external_tfx.py from {src.name})", "",
             f"{len(df):,} rows: Japanese retail FX positions on the Tokyo Financial Exchange (Click 365), one row per pair per "
             "Tuesday. Columns: pair (TFX code, e.g. USD/JPY; USL/JPY etc. are the LARGE contracts), symbol (our price-store "
             "symbol or null), ts_asof (Tuesday, position at the close of that trading day), sell and buy (customers' open short "
             "and long contracts), oi = sell + buy, net = buy - sell, long_share = buy / oi, ts_avail (= ts_asof + "
             f"{LAG_DAYS} days 00:00 UTC; the file is republished on the following Tuesday, hour unverified).", "",
             f"Source: {URL} (TFX, 為替売買動向, weekly). Contract sizes differ by pair, so compare long_share and "
             "net within a pair only. This is the only long/short split TFX publishes; its daily reports and 2010-2021 monthly "
             "statistics carry total open interest only. Click 365 is a minority of Japanese retail FX (the OTC brokers are "
             "larger) and the only venue that publishes positions, so treat it as a proxy for the retail yen-cross book.", ""]
    lines += [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> None:
    src = fetch() if "--fetch" in argv else newest_raw()
    df = parse(src)
    notes = check(df)
    EXT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(EXT / "tfx.parquet", index=False)
    text = readme(src, df, notes)
    (EXT / "tfx" / "README.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
