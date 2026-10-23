"""The strategy contract: vectorised signals decided at bar close, executed from the next bar.

A strategy module defines

    NAME = "my_strategy"
    PARAMS = {"lookback": 20, "k": 1.5}            # defaults
    GRID = {"lookback": [10, 20, 40], "k": [1.0, 1.5, 2.0]}   # optional search space
    def signals(m: Market, p: dict) -> Signals: ...

Everything in `Signals` is indexed by bar. A value at index i may only use information from bars
0..i (the bar that has just closed). The executor acts on it from bar i+1 onwards:

    entry_long[i]  / entry_short[i]   place an entry order after bar i closes
    entry_type[i]                     0 = market at next open, 1 = stop, 2 = limit
    entry_price_long[i]               trigger price of a long stop/limit order (ask side)
    entry_price_short[i]              trigger price of a short stop/limit order (bid side)
    valid_bars[i]                     how many bars a pending stop/limit stays working (market: 1)
    sl_dist[i]                        stop distance in price units, measured from the fill (> 0, required)
    tp_dist[i]                        take-profit distance in price units (NaN = none)
    max_bars[i]                       close at the open of the bar after holding this many bars (0 = none)
    exit_long[i] / exit_short[i]      close an open position at the next bar's open

Long and short entries on the same bar form an OCO pair: the first fill cancels the other.
While a position is open, new entry signals are ignored (no pyramiding, no reversal).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Protocol

import numpy as np

from .market import Market

MARKET, STOP, LIMIT = 0, 1, 2

_FIELDS = ("entry_long", "entry_short", "entry_type", "entry_price_long", "entry_price_short", "valid_bars",
           "sl_dist", "tp_dist", "max_bars", "exit_long", "exit_short")
_DTYPES = {
    "entry_long": np.bool_, "entry_short": np.bool_, "entry_type": np.int8,
    "entry_price_long": np.float64, "entry_price_short": np.float64, "valid_bars": np.int32,
    "sl_dist": np.float64, "tp_dist": np.float64, "max_bars": np.int32,
    "exit_long": np.bool_, "exit_short": np.bool_,
}


@dataclass
class Signals:
    n: int
    entry_long: np.ndarray = field(default=None)
    entry_short: np.ndarray = field(default=None)
    entry_type: np.ndarray = field(default=None)
    entry_price_long: np.ndarray = field(default=None)
    entry_price_short: np.ndarray = field(default=None)
    valid_bars: np.ndarray = field(default=None)
    sl_dist: np.ndarray = field(default=None)
    tp_dist: np.ndarray = field(default=None)
    max_bars: np.ndarray = field(default=None)
    exit_long: np.ndarray = field(default=None)
    exit_short: np.ndarray = field(default=None)

    def __post_init__(self) -> None:
        n = self.n
        defaults = {
            "entry_long": lambda: np.zeros(n, dtype=np.bool_),
            "entry_short": lambda: np.zeros(n, dtype=np.bool_),
            "entry_type": lambda: np.zeros(n, dtype=np.int8),
            "entry_price_long": lambda: np.full(n, np.nan),
            "entry_price_short": lambda: np.full(n, np.nan),
            "valid_bars": lambda: np.ones(n, dtype=np.int32),
            "sl_dist": lambda: np.full(n, np.nan),
            "tp_dist": lambda: np.full(n, np.nan),
            "max_bars": lambda: np.zeros(n, dtype=np.int32),
            "exit_long": lambda: np.zeros(n, dtype=np.bool_),
            "exit_short": lambda: np.zeros(n, dtype=np.bool_),
        }
        for name in _FIELDS:
            if getattr(self, name) is None:
                setattr(self, name, defaults[name]())
        self._coerce()

    def _coerce(self) -> None:
        for name in _FIELDS:
            arr = np.ascontiguousarray(getattr(self, name), dtype=_DTYPES[name])
            if arr.shape != (self.n,):
                raise ValueError(f"Signals.{name} has shape {arr.shape}, expected ({self.n},)")
            setattr(self, name, arr)

    def validate(self) -> None:
        """Cheap sanity checks that catch most strategy bugs before the executor runs."""
        self._coerce()
        has_entry = self.entry_long | self.entry_short
        if has_entry.any():
            bad_sl = has_entry & ~(self.sl_dist > 0)
            if bad_sl.any():
                raise ValueError(f"{int(bad_sl.sum())} entries have no positive sl_dist")
            pend_long = self.entry_long & (self.entry_type != MARKET)
            if pend_long.any() and not np.isfinite(self.entry_price_long[pend_long]).all():
                raise ValueError("long stop/limit entries need a finite entry_price_long")
            pend_short = self.entry_short & (self.entry_type != MARKET)
            if pend_short.any() and not np.isfinite(self.entry_price_short[pend_short]).all():
                raise ValueError("short stop/limit entries need a finite entry_price_short")
            if (self.valid_bars[has_entry] < 1).any():
                raise ValueError("valid_bars must be >= 1 where an entry is signalled")
        if (self.max_bars < 0).any():
            raise ValueError("max_bars must be >= 0")

    @property
    def n_entries(self) -> int:
        return int((self.entry_long | self.entry_short).sum())


class StrategyModule(Protocol):
    NAME: str
    PARAMS: dict

    def signals(self, m: Market, p: dict) -> Signals: ...


def run_signals(mod: ModuleType, m: Market, params: dict | None = None) -> Signals:
    p = dict(getattr(mod, "PARAMS", {}))
    if params:
        p.update(params)
    sig = mod.signals(m, p)
    if not isinstance(sig, Signals):
        raise TypeError(f"{mod.__name__}.signals must return Signals, got {type(sig).__name__}")
    if sig.n != m.n:
        raise ValueError(f"Signals.n={sig.n} but market has {m.n} bars")
    sig.validate()
    return sig
