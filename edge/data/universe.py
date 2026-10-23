"""Instrument universe: symbols, Dukascopy codes, price scales, pip sizes, asset classes.

Dukascopy stores prices as integers. JPY pairs, metals and index CFDs use 3 decimals
(scale 1000); every other FX pair uses 5 decimals (scale 100000).
"""
from __future__ import annotations

FX_MAJORS: list[str] = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]

FX_MINORS: list[str] = [
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "CADJPY", "CADCHF", "CHFJPY",
    "NZDJPY", "NZDCHF", "NZDCAD",
]

METALS: list[str] = ["XAUUSD", "XAGUSD"]

# Dukascopy index CFD code -> common name
INDICES: dict[str, str] = {
    "USA500IDXUSD": "US500",
    "USATECHIDXUSD": "US100",
    "USA30IDXUSD": "US30",
    "DEUIDXEUR": "GER40",
    "GBRIDXGBP": "UK100",
    "JPNIDXJPY": "JP225",
}

FX_ALL: list[str] = FX_MAJORS + FX_MINORS
ALL_SYMBOLS: list[str] = FX_ALL + METALS + list(INDICES)

# Currencies quoted as USDXXX on Dukascopy (quote currency per 1 USD is the pair price itself).
_USD_BASE_QUOTES = {"JPY", "CHF", "CAD"}
# Currencies quoted as XXXUSD (quote currency per 1 USD is 1 / pair price).
_USD_QUOTE_BASES = {"EUR", "GBP", "AUD", "NZD"}


def asset_class(sym: str) -> str:
    sym = sym.upper()
    if "IDX" in sym:
        return "index"
    if sym.startswith(("XAU", "XAG")):
        return "metal"
    return "fx"


def price_scale(sym: str) -> float:
    """Divisor that turns Dukascopy integer prices into real prices."""
    sym = sym.upper()
    if sym.endswith("JPY") or asset_class(sym) != "fx":
        return 1000.0
    return 100000.0


def point_size(sym: str) -> float:
    """Smallest price increment in the Dukascopy feed."""
    return 1.0 / price_scale(sym)


def pip_size(sym: str) -> float:
    """Conventional pip: 0.01 for JPY pairs and metals, 1 index point for indices, else 0.0001."""
    sym = sym.upper()
    cls = asset_class(sym)
    if cls == "index":
        return 1.0
    if cls == "metal":
        return 0.01
    return 0.01 if sym.endswith("JPY") else 0.0001


def base_quote(sym: str) -> tuple[str, str]:
    sym = sym.upper()
    if "IDX" in sym:
        return sym[:-3], sym[-3:]
    return sym[:3], sym[3:]


def quote_currency(sym: str) -> str:
    return base_quote(sym)[1]


def conversion_pair(sym: str) -> tuple[str | None, bool]:
    """Pair whose price converts the quote currency to USD.

    Returns (pair, invert). quote_per_usd = price(pair) if not invert else 1 / price(pair).
    (None, False) when the quote currency is already USD.
    """
    quote = quote_currency(sym)
    if quote == "USD":
        return None, False
    if quote in _USD_BASE_QUOTES:
        return f"USD{quote}", False
    if quote in _USD_QUOTE_BASES:
        return f"{quote}USD", True
    raise ValueError(f"no USD conversion pair known for {sym}")


def validate_symbol(sym: str) -> str:
    s = sym.upper()
    if s not in ALL_SYMBOLS:
        raise ValueError(f"unknown symbol {sym!r}; known: {', '.join(ALL_SYMBOLS)}")
    return s
