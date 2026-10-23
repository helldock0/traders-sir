"""Build the external (non-price) research inputs. Every table carries `ts_avail`, the UTC time from which a
row may be used by a strategy (the release time, never the observation time).

  calendar  scheduled macro releases with consensus and actual values and standardised surprises.
            2010-2023: ForexFactory scrape by spoluan (github.com/spoluan/forex-factory-scraper, per-year CSVs);
            its times are UTC+8 with no daylight saving (verified: US NFP and CPI land on 12:30 / 13:30 UTC).
            2024-01-01 .. 2025-04-07: ForexFactory snapshot by Ehsanrs2 on Hugging Face (ISO timestamps with offset).
            Rows whose wall-clock time is 00:00:00 carry no time: the time is backfilled from the same event's modal
            UTC time in the same calendar month of 2019-2023 (time_source = typical), else the row is usable only
            from the next day. The two sources agree on 99.7% of actual and forecast values where they overlap.
  cot       CFTC Traders in Financial Futures (7 currencies, USD index, E-mini S&P 500, Nasdaq-100 mini) and the
            Disaggregated report (COMEX gold): Tuesday positions, usable from the Friday 15:30 ET release
            (three US business days later; holiday closures and shutdown catch-ups as in the prior gj-strat
            cot_positioning research, catch-up weeks usable only from the end of the catch-up).
  vol       CBOE implied-volatility indices from FRED (VIXCLS, VXNCLS, EVZCLS, GVZCLS, OVXCLS): daily close,
            usable from 21:30 UTC on the observation date (CBOE settles 16:15 New York).
Outputs data/external/{calendar,cot,vol}.parquet and data/external/README.md.

    .venv/Scripts/python.exe -I scripts/build_external.py
"""
from __future__ import annotations

import glob
import io
import re
import sys
import zipfile
from pathlib import Path

import holidays
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
TODAY = "2026-10-14"

# ----------------------------------------------------------------------------------------------- calendar
IMPACT = {"high": "high", "high impact expected": "high", "medium": "medium", "medium impact expected": "medium",
          "low": "low", "low impact expected": "low", "non-economic": "none", "holiday": "none"}
UNIT = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
NUM_RE = re.compile(r"^[<>]?\s*(-?\d+(?:\.\d+)?)\s*([KMBT%]?)")


def parse_num(s) -> float:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan
    x = str(s).strip().replace(",", "")
    m = NUM_RE.match(x)
    if not m:
        return np.nan
    return float(m.group(1)) * UNIT.get(m.group(2), 1.0)


def norm_impact(s: pd.Series) -> pd.Series:
    return s.fillna("").str.strip().str.lower().map(IMPACT).fillna("none")


def load_spoluan() -> pd.DataFrame:
    files = sorted(glob.glob(str(EXT / "calendar_spoluan" / "forex_factory_calendar_*.csv")))
    df = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
    df = df[df["Date"].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)].copy()
    t = pd.to_datetime(df["Date"] + " " + df["Time"].fillna("").str.strip(), format="%Y-%m-%d %I:%M%p", errors="coerce")
    known = t.notna()
    date_local = pd.to_datetime(df["Date"])
    ts_release = (t - pd.Timedelta(hours=8)).where(known, date_local - pd.Timedelta(hours=8))
    ts_avail = ts_release.where(known, date_local + pd.Timedelta(days=1) - pd.Timedelta(hours=8))
    return pd.DataFrame({"ts_release": ts_release, "ts_avail": ts_avail, "time_known": known.to_numpy(),
                         "time_source": np.where(known, "scraped", "unknown"),
                         "currency": df["Currency"].str.strip(), "event": df["Event"].str.strip(),
                         "impact": norm_impact(df["Impact"]), "actual": df["Actual"], "forecast": df["Forecast"],
                         "previous": df["Previous"], "source": "ff_spoluan"})


def load_hf(start: str) -> pd.DataFrame:
    hf = pd.read_csv(EXT / "calendar_hf" / "forex_factory_cache.csv", dtype=str)
    dt = pd.to_datetime(hf["DateTime"], utc=True, errors="coerce").dt.tz_convert(None)
    wall = hf["DateTime"].str.slice(11, 19)
    known = ~wall.isin(["00:00:00", "23:59:59"]) & dt.notna()
    date_local = pd.to_datetime(hf["DateTime"].str.slice(0, 10))
    out = pd.DataFrame({"ts_release": dt.where(known, date_local), "ts_avail": dt.where(known, date_local + pd.Timedelta(days=1)),
                        "time_known": known.to_numpy(), "time_source": np.where(known, "scraped", "unknown"),
                        "currency": hf["Currency"].str.strip(), "event": hf["Event"].str.strip(), "impact": norm_impact(hf["Impact"]),
                        "actual": hf["Actual"], "forecast": hf["Forecast"], "previous": hf["Previous"], "source": "ff_hf"})
    return out[out["ts_release"] >= pd.Timestamp(start)].copy()


def backfill_times(hf: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    """Give time-less rows the modal UTC time of day of the same (currency, event) in the same month of 2019-2023."""
    h = hist[hist["time_known"] & (hist["ts_release"] >= "2019-01-01")].copy()
    h["month"] = h["ts_release"].dt.month
    h["tod"] = h["ts_release"].dt.hour * 60 + h["ts_release"].dt.minute
    typical = h.groupby(["currency", "event", "month"])["tod"].agg(lambda s: int(s.mode().iloc[0])).rename("tod")
    hf = hf.copy()
    hf["month"] = hf["ts_release"].dt.month
    hf = hf.join(typical, on=["currency", "event", "month"])
    fill = ~hf["time_known"] & hf["tod"].notna()
    base = hf["ts_release"].dt.normalize()
    hf.loc[fill, "ts_release"] = base[fill] + pd.to_timedelta(hf.loc[fill, "tod"], unit="m")
    hf.loc[fill, "ts_avail"] = hf.loc[fill, "ts_release"]
    hf.loc[fill, "time_source"] = "typical"
    hf.loc[fill, "time_known"] = True
    return hf.drop(columns=["month", "tod"])


def add_surprises(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["currency", "event", "ts_release"]).reset_index(drop=True)
    for c in ("actual", "forecast", "previous"):
        df[f"{c}_num"] = df[c].map(parse_num)
    df["surprise"] = df["actual_num"] - df["forecast_num"]
    g = df.groupby(["currency", "event"], sort=False)["surprise"]
    sd_prev = g.transform(lambda s: s.shift(1).expanding(min_periods=8).std())
    df["surprise_z"] = df["surprise"] / sd_prev
    df.loc[~np.isfinite(df["surprise_z"]), "surprise_z"] = np.nan
    return df


def build_calendar() -> tuple[pd.DataFrame, list[str]]:
    sp = load_spoluan()
    hf = backfill_times(load_hf("2024-01-01"), sp)
    cal = pd.concat([sp, hf], ignore_index=True)
    cal = cal.drop_duplicates(["ts_release", "currency", "event"], keep="first")
    cal = add_surprises(cal)
    cal = cal.sort_values(["ts_avail", "currency", "event"]).reset_index(drop=True)
    notes = []
    nfp = cal[(cal["currency"] == "USD") & (cal["event"] == "Non-Farm Employment Change") & cal["time_known"]]
    tod = nfp["ts_release"].dt.strftime("%H:%M").value_counts().head(4).to_dict()
    notes.append(f"US Non-Farm Employment Change release times (UTC): {tod} over {len(nfp)} rows")
    nfp24 = nfp[nfp["ts_release"] >= "2024-01-01"]["ts_release"].dt.strftime("%Y-%m-%d %H:%M").head(6).tolist()
    notes.append(f"2024+ NFP timestamps: {nfp24}")
    hi = cal[cal["impact"] == "high"]
    notes.append(f"high-impact rows per year: {hi['ts_release'].dt.year.value_counts().sort_index().to_dict()}")
    notes.append(f"time_source counts: {cal['time_source'].value_counts().to_dict()}")
    both = hi[hi["actual_num"].notna() & hi["forecast_num"].notna()]
    notes.append(f"high-impact rows with numeric actual and forecast: {len(both)} of {len(hi)}; with surprise_z: {int(both['surprise_z'].notna().sum())}")
    return cal, notes


# ----------------------------------------------------------------------------------------------- CFTC COT
TFF_CODES = {"099741": "EUR", "097741": "JPY", "096742": "GBP", "092741": "CHF", "090741": "CAD", "232741": "AUD",
             "112741": "NZD", "098662": "USDX", "13874A": "SPX", "209742": "NDX"}
DISAGG_CODES = {"088691": "GOLD"}
DAY = pd.Timedelta(days=1)
US_HOL = {pd.Timestamp(d) for d in holidays.US(years=range(2009, 2028))}
CLOSURES = {pd.Timestamp(d) for d in ["2009-01-20", "2012-12-24", "2014-12-26", "2015-12-24", "2017-01-20", "2018-12-05",
                                      "2018-12-24", "2019-12-24", "2020-12-24", "2021-01-20", "2024-12-24", "2025-01-09"]}
# (first T, last T, usable from): reports delayed by shutdowns / the 2023 ION incident, usable once the catch-up ended
CATCH_UP = [("2013-09-30", "2013-11-12", "2013-11-15"), ("2018-12-17", "2019-03-05", "2019-03-08"),
            ("2023-01-31", "2023-03-14", "2023-03-21"), ("2025-09-29", "2026-01-13", "2026-01-20")]
OFFICIAL = {"2011-11-08": "2011-11-14", "2014-12-23": "2014-12-30", "2015-06-30": "2015-07-06", "2018-12-24": "2018-12-28",
            "2018-12-31": "2019-01-04", "2020-12-21": "2020-12-28", "2021-06-15": "2021-06-21", "2025-01-07": "2025-01-13"}


def us_bday(d: pd.Timestamp) -> bool:
    return d.dayofweek < 5 and d not in US_HOL and d not in CLOSURES


def release_date(T: pd.Timestamp) -> pd.Timestamp:
    key = T.strftime("%Y-%m-%d")
    if key in OFFICIAL:
        return pd.Timestamp(OFFICIAL[key])
    for a, b, use in CATCH_UP:
        if pd.Timestamp(a) <= T <= pd.Timestamp(b):
            return pd.Timestamp(use)
    d, n = T, 0
    while n < 3:
        d += DAY
        n += us_bday(d)
    return d


def et_to_utc(day: pd.Timestamp, hh: int, mm: int) -> pd.Timestamp:
    return (day + pd.Timedelta(hours=hh, minutes=mm)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)


def read_cot(kind: str) -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(str(EXT / "cftc" / f"fut_{kind}_txt_*.zip"))):
        z = zipfile.ZipFile(f)
        frames.append(pd.read_csv(io.BytesIO(z.open(z.namelist()[0]).read()), dtype=str, low_memory=False))
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    df["code"] = df["CFTC_Contract_Market_Code"].str.strip()
    return df


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.strip().str.replace(",", ""), errors="coerce")


def asof_date(df: pd.DataFrame) -> pd.Series:
    """Tuesday as-of date; the 2010-2012 files fill only the YYMMDD column."""
    a = pd.to_datetime(df["Report_Date_as_YYYY-MM-DD"].str.strip(), errors="coerce")
    b = pd.to_datetime(df["As_of_Date_In_Form_YYMMDD"].str.strip(), format="%y%m%d", errors="coerce")
    return a.fillna(b)


def build_cot() -> tuple[pd.DataFrame, list[str]]:
    tff = read_cot("fin")
    tff = tff[tff["code"].isin(TFF_CODES)].copy()
    names = tff.groupby("code")["Market_and_Exchange_Names"].first().to_dict()
    t = pd.DataFrame({
        "market": tff["code"].map(TFF_CODES), "ts_asof": asof_date(tff),
        "oi": num(tff["Open_Interest_All"]),
        "spec_long": num(tff["Lev_Money_Positions_Long_All"]), "spec_short": num(tff["Lev_Money_Positions_Short_All"]),
        "inst_long": num(tff["Asset_Mgr_Positions_Long_All"]), "inst_short": num(tff["Asset_Mgr_Positions_Short_All"]),
        "comm_long": num(tff["Dealer_Positions_Long_All"]), "comm_short": num(tff["Dealer_Positions_Short_All"]),
        "other_long": num(tff["Other_Rept_Positions_Long_All"]), "other_short": num(tff["Other_Rept_Positions_Short_All"]),
        "nonrept_long": num(tff["NonRept_Positions_Long_All"]), "nonrept_short": num(tff["NonRept_Positions_Short_All"]),
        "report": "tff"})
    dis = read_cot("disagg")
    dis = dis[dis["code"].isin(DISAGG_CODES)].copy()
    names.update(dis.groupby("code")["Market_and_Exchange_Names"].first().to_dict())
    d = pd.DataFrame({
        "market": dis["code"].map(DISAGG_CODES), "ts_asof": asof_date(dis),
        "oi": num(dis["Open_Interest_All"]),
        "spec_long": num(dis["M_Money_Positions_Long_All"]), "spec_short": num(dis["M_Money_Positions_Short_All"]),
        "inst_long": num(dis["Swap_Positions_Long_All"]), "inst_short": num(dis["Swap__Positions_Short_All"]),
        "comm_long": num(dis["Prod_Merc_Positions_Long_All"]), "comm_short": num(dis["Prod_Merc_Positions_Short_All"]),
        "other_long": num(dis["Other_Rept_Positions_Long_All"]), "other_short": num(dis["Other_Rept_Positions_Short_All"]),
        "nonrept_long": num(dis["NonRept_Positions_Long_All"]), "nonrept_short": num(dis["NonRept_Positions_Short_All"]),
        "report": "disagg"})
    cot = pd.concat([t, d], ignore_index=True)
    n_nat = int(cot["ts_asof"].isna().sum())
    cot = cot[cot["ts_asof"].notna()].drop_duplicates(["market", "ts_asof"], keep="last")
    for g in ("spec", "inst", "comm", "other", "nonrept"):
        cot[f"{g}_net"] = cot[f"{g}_long"] - cot[f"{g}_short"]
        cot[f"{g}_net_oi"] = cot[f"{g}_net"] / cot["oi"]
    rel = cot["ts_asof"].map(release_date)
    cot["ts_release_date"] = rel
    cot["ts_avail"] = [et_to_utc(r, 15, 30) for r in rel]
    cot = cot.sort_values(["ts_avail", "market"]).reset_index(drop=True)
    notes = [f"contracts: {names}", f"rows without an as-of date dropped: {n_nat}",
             f"rows per market: {cot['market'].value_counts().to_dict()}",
             f"as-of range: {cot['ts_asof'].min().date()} .. {cot['ts_asof'].max().date()}; "
             f"release lag days: {(cot['ts_release_date'] - cot['ts_asof']).dt.days.value_counts().sort_index().to_dict()}"]
    return cot, notes


# ----------------------------------------------------------------------------------------------- FRED vol
VOL = {"VIXCLS": "vix", "VXNCLS": "vxn", "EVZCLS": "evz", "GVZCLS": "gvz", "OVXCLS": "ovx"}


def build_vol() -> tuple[pd.DataFrame, list[str]]:
    wide = None
    for sid, col in VOL.items():
        df = pd.read_csv(EXT / "fred" / f"{sid}.csv", dtype=str)
        df = pd.DataFrame({"date": pd.to_datetime(df["observation_date"]), col: pd.to_numeric(df[sid], errors="coerce")})
        wide = df if wide is None else wide.merge(df, on="date", how="outer")
    wide = wide.sort_values("date").reset_index(drop=True)
    wide = wide[wide["date"] >= "2009-01-01"].copy()
    wide["ts_avail"] = wide["date"] + pd.Timedelta(hours=21, minutes=30)
    wide = wide[["ts_avail", "date"] + list(VOL.values())]
    notes = [f"range {wide['date'].min().date()} .. {wide['date'].max().date()}, {len(wide)} days; "
             f"missing per series: {wide[list(VOL.values())].isna().sum().to_dict()}"]
    return wide, notes


# ----------------------------------------------------------------------------------------------- main
def main() -> None:
    cal, cal_notes = build_calendar()
    cal.to_parquet(EXT / "calendar.parquet", index=False)
    cot, cot_notes = build_cot()
    cot.to_parquet(EXT / "cot.parquet", index=False)
    vol, vol_notes = build_vol()
    vol.to_parquet(EXT / "vol.parquet", index=False)
    lines = [f"# External inputs (built {TODAY} by scripts/build_external.py)", "",
             "Every table has `ts_avail` (UTC, naive): the first moment a row may be used. Strategies read these through "
             "`F.ext_asof` / `F.ext_rows` (see edge/engine/features.py); the leak tests cut and perturb them at the primary "
             "bar's close like auxiliary markets.", "",
             "## calendar.parquet", "",
             f"{len(cal):,} rows, {cal['ts_release'].min().date()} .. {cal['ts_release'].max().date()}. Columns: ts_release, ts_avail, "
             "time_known, time_source (scraped / typical / unknown), currency, event, impact (high / medium / low / none), actual, "
             "forecast, previous (strings as published), actual_num, forecast_num, previous_num (K/M/B/T scaled, % kept as the "
             "number), surprise = actual - forecast, surprise_z = surprise / std of that event's earlier surprises (at least 8), source.", "",
             "Sources: 2010-2023 github.com/spoluan/forex-factory-scraper (datasets/forex_factory_calendar_YYYY.csv, ForexFactory "
             "scrape, times UTC+8 without daylight saving); 2024-01-01 .. 2025-04-07 huggingface.co/datasets/Ehsanrs2/"
             "Forex_Factory_Calendar (forex_factory_cache.csv, MIT licence on the file, ForexFactory scrape). ForexFactory's own "
             "terms apply to the underlying data: private research use only. No source after 2025-04-07 yet.", ""]
    lines += [f"- {n}" for n in cal_notes]
    lines += ["", "## cot.parquet", "",
              f"{len(cot):,} rows, Tuesday positions {cot['ts_asof'].min().date()} .. {cot['ts_asof'].max().date()}. Columns: market "
              "(EUR, JPY, GBP, CHF, CAD, AUD, NZD, USDX, SPX, NDX from the Traders in Financial Futures report; GOLD from the "
              "Disaggregated report), ts_asof, ts_release_date, ts_avail (15:30 New York on the release date), oi, and per group "
              "long / short / net / net_oi: spec (leveraged funds; managed money for gold), inst (asset managers; swap dealers for "
              "gold), comm (dealers; producers for gold), other, nonrept.", "",
              "Source: cftc.gov/files/dea/history/fut_fin_txt_YYYY.zip and fut_disagg_txt_YYYY.zip, 2010-2026, public domain. "
              "Release dates: three US business days after the Tuesday (CFTC closures and holiday shifts from the gj-strat "
              "cot_positioning research); the 2013, 2018-19 and 2025 shutdown weeks and the 2023 ION-incident weeks are usable "
              "only from the end of their catch-up. gj-strat already tested positioning as a standalone signal (8 variants, "
              "negative); use it as a conditioning state.", ""]
    lines += [f"- {n}" for n in cot_notes]
    lines += ["", "## vol.parquet", "",
              "Daily CBOE implied-volatility closes from FRED: vix (S&P 500), vxn (Nasdaq-100), evz (EuroCurrency ETF, i.e. EURUSD "
              "implied vol), gvz (gold), ovx (oil). Columns: ts_avail (21:30 UTC on the observation date), date, vix, vxn, evz, gvz, ovx.", "",
              "Source: fred.stlouisfed.org/graph/fredgraph.csv?id=<series>, downloaded " + TODAY + ". FRED terms: non-commercial use.", ""]
    lines += [f"- {n}" for n in vol_notes]
    (EXT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
