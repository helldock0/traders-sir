"""Trading costs expressed in R so results do not depend on account size.

  * Spread is already inside the fills (longs buy the ask, exit on the bid).
  * Slippage is applied inside the executor on market and stop fills (price units).
  * Commission: USD per lot round turn. In R: commission / risk_usd_per_lot, where
    risk_usd_per_lot = stop distance x contract size / quote_per_usd at entry.
  * Swap / financing: one night of interest per 17:00 New York rollover held, three on Wednesday.
    FX: long earns base rate and pays quote rate, minus a broker markup (both sides pay it).
    Metals and indices: long pays (quote rate + CFD markup), short receives (quote rate - CFD markup).
    Rates are FRED series forward-filled to daily; the rate as of the entry day is used for the whole
    trade (trades here last hours to days).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from ..data import store
from ..data.universe import asset_class, base_quote
from .market import Market

RATES_DIR = store.DATA_DIR / "rates"
FRED_FILES = {
    "USD": "DFF.csv", "JPY": "IRSTCI01JPM156N.csv", "EUR": "IRSTCI01EZM156N.csv", "GBP": "IRSTCI01GBM156N.csv",
    "AUD": "IRSTCI01AUM156N.csv", "CAD": "IRSTCI01CAM156N.csv", "CHF": "IR3TIB01CHM156N.csv", "NZD": "IR3TIB01NZM156N.csv",
}
NY = ZoneInfo("America/New_York")


def contract_size(sym: str) -> float:
    cls = asset_class(sym)
    if cls == "fx":
        return 100_000.0
    if sym.upper().startswith("XAU"):
        return 100.0
    if sym.upper().startswith("XAG"):
        return 5_000.0
    return 1.0


@dataclass
class CostModel:
    commission_per_lot_usd: float = 7.0      # FX round turn; set 0 for commission-free CFDs
    commission_per_lot_usd_cfd: float = 0.0  # metals and indices
    slippage_pips: float = 0.2               # FX, applied to market and stop fills
    slippage_points_cfd: float = 1.0         # metals/indices, in pips as defined by universe.pip_size
    swap_markup_pct: float = 1.0             # FX: broker spread on the rate differential, % per year
    cfd_financing_markup_pct: float = 2.5    # metals/indices: % per year over the quote rate
    include_swap: bool = True
    rates_dir: Path = field(default=RATES_DIR)

    def slippage_price(self, m: Market) -> float:
        pips = self.slippage_pips if m.asset == "fx" else self.slippage_points_cfd
        return pips * m.pip

    def commission(self, m: Market) -> float:
        return self.commission_per_lot_usd if m.asset == "fx" else self.commission_per_lot_usd_cfd


class Rates:
    """Daily forward-filled policy rates (% per year) per currency."""

    def __init__(self, folder: Path = RATES_DIR):
        self.series: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for ccy, fname in FRED_FILES.items():
            path = folder / fname
            if not path.exists():
                continue
            df = pl.read_csv(path, try_parse_dates=True)
            vals = df.get_column(df.columns[1]).cast(pl.Float64, strict=False)
            d = df.get_column(df.columns[0])
            ok = vals.is_not_null()
            days = d.filter(ok).to_numpy().astype("datetime64[D]")
            self.series[ccy] = (days, vals.filter(ok).to_numpy().astype(np.float64))

    def rate(self, ccy: str, days: np.ndarray) -> np.ndarray:
        """Rate as of each day (datetime64[D]); 0 if the currency has no series."""
        if ccy not in self.series:
            return np.zeros(len(days))
        d, v = self.series[ccy]
        idx = np.searchsorted(d, days, side="right") - 1
        idx = np.clip(idx, 0, len(v) - 1)
        return v[idx]


_ROLL_CACHE: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}


def rollovers(year_from: int = 2005, year_to: int = 2032) -> tuple[np.ndarray, np.ndarray]:
    """UTC timestamps of every weekday 17:00 New York rollover and cumulative night weights (Wed = 3)."""
    key = (year_from, year_to)
    if key in _ROLL_CACHE:
        return _ROLL_CACHE[key]
    ts, w = [], []
    d = date(year_from, 1, 1)
    end = date(year_to, 12, 31)
    while d <= end:
        if d.weekday() < 5:
            local = datetime(d.year, d.month, d.day, 17, 0, tzinfo=NY)
            ts.append(np.datetime64(local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None), "us"))
            w.append(3 if d.weekday() == 2 else 1)
        d += timedelta(days=1)
    roll = np.array(ts, dtype="datetime64[us]")
    cumw = np.concatenate([[0], np.cumsum(np.array(w, dtype=np.int64))])
    _ROLL_CACHE[key] = (roll, cumw)
    return roll, cumw


def nights_held(entry_ts: np.ndarray, exit_ts: np.ndarray) -> np.ndarray:
    roll, cumw = rollovers()
    a = np.searchsorted(roll, entry_ts.astype("datetime64[us]"), side="right")
    b = np.searchsorted(roll, exit_ts.astype("datetime64[us]"), side="right")
    return cumw[b] - cumw[a]


def apply_costs(trades: pl.DataFrame, m: Market, cm: CostModel, rates: Rates | None = None) -> pl.DataFrame:
    """Add comm_r, swap_r, nights and r_net to a trades frame from the executor."""
    if trades.height == 0:
        return trades.with_columns(
            pl.lit(0.0).alias("comm_r"), pl.lit(0.0).alias("swap_r"),
            pl.lit(0, dtype=pl.Int64).alias("nights"), pl.col("r_gross").alias("r_net"),
        )
    size = contract_size(m.sym)
    risk = trades.get_column("risk").to_numpy()
    qpu = trades.get_column("quote_per_usd").to_numpy()
    entry_px = trades.get_column("entry_px").to_numpy()
    side = trades.get_column("side").to_numpy().astype(np.float64)
    risk_usd_per_lot = risk * size / qpu
    comm_r = cm.commission(m) / risk_usd_per_lot

    swap_r = np.zeros(len(risk))
    nights = np.zeros(len(risk), dtype=np.int64)
    if cm.include_swap:
        rates = rates or Rates(cm.rates_dir)
        e_ts = trades.get_column("entry_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
        x_ts = trades.get_column("exit_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
        nights = nights_held(e_ts, x_ts)
        days = e_ts.astype("datetime64[D]")
        base, quote = base_quote(m.sym)
        r_quote = rates.rate(quote, days)
        notional_usd_per_lot = size * entry_px / qpu
        if m.asset == "fx":
            r_base = rates.rate(base, days)
            diff = r_base - r_quote
            rate = np.where(side > 0, diff, -diff) - cm.swap_markup_pct
        else:
            rate = np.where(side > 0, -(r_quote + cm.cfd_financing_markup_pct), r_quote - cm.cfd_financing_markup_pct)
        swap_usd_per_lot = notional_usd_per_lot * rate / 100.0 * nights / 365.0
        swap_r = swap_usd_per_lot / risk_usd_per_lot
    return trades.with_columns(
        pl.Series("comm_r", comm_r), pl.Series("swap_r", swap_r), pl.Series("nights", nights),
    ).with_columns((pl.col("r_gross") - pl.col("comm_r") + pl.col("swap_r")).alias("r_net"))
