"""Dukascopy raw datafeed: one LZMA-compressed file per instrument, UTC day and side.

    https://datafeed.dukascopy.com/datafeed/{SYM}/{YYYY}/{MM-1:02d}/{DD:02d}/{BID|ASK}_candles_min_1.bi5

Each record is big-endian: int32 seconds from midnight UTC, int32 open, close, low, high
(scaled integers, see universe.price_scale), float32 tick volume. Minutes without ticks come
back as flat candles with volume 0; the decoder drops those filler minutes.

Raw files are kept on disk as {SYM}_{YYYYMMDD}_{SIDE}.bi5, the same layout the gj-strat
datastore uses, so its tars extract straight into our raw folder. A zero-byte file marks a
day the server has no data for (404), so it is not requested again.
"""
from __future__ import annotations

import logging
import lzma
import random
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import polars as pl

from .universe import price_scale

log = logging.getLogger(__name__)

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
CANDLE_DTYPE = np.dtype(
    [("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"), ("h", ">i4"), ("v", ">f4")]
)
SIDES = ("BID", "ASK")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
RETRY_STATUSES = {403, 408, 425, 429, 500, 502, 503, 504}


def day_url(sym: str, day: date, side: str) -> str:
    # Dukascopy months are zero-based in the URL.
    return f"{BASE_URL}/{sym}/{day.year}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def raw_file_name(sym: str, day: date, side: str) -> str:
    return f"{sym}_{day:%Y%m%d}_{side}.bi5"


def parse_raw_file_name(name: str) -> tuple[str, date, str]:
    stem = name[:-4] if name.endswith(".bi5") else name
    sym, ymd, side = stem.split("_")
    return sym, datetime.strptime(ymd, "%Y%m%d").date(), side


class Bi5Client:
    """Polite, resumable downloader. One request at a time, paced, with exponential backoff."""

    def __init__(self, pace_s: float = 0.6, max_attempts: int = 12, timeout_s: float = 60.0):
        self.pace_s = pace_s
        self.max_attempts = max_attempts
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=timeout_s,
            follow_redirects=True,
        )
        self._last_request = 0.0
        self.stats = {"ok": 0, "cached": 0, "404": 0, "retries": 0, "failed": 0}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Bi5Client":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _pace(self) -> None:
        wait = self.pace_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

    def fetch(self, url: str) -> bytes | None:
        """Return the file bytes, or None when the server has no file (404)."""
        for attempt in range(self.max_attempts):
            self._pace()
            try:
                r = self._client.get(url)
                self._last_request = time.monotonic()
                if r.status_code == 200:
                    return r.content
                if r.status_code == 404:
                    return None
                if r.status_code not in RETRY_STATUSES:
                    r.raise_for_status()
                reason = f"HTTP {r.status_code}"
            except httpx.HTTPError as exc:
                self._last_request = time.monotonic()
                reason = f"{type(exc).__name__}: {exc}"
            self.stats["retries"] += 1
            delay = min(2**attempt, 90) + random.random()
            if attempt % 3 == 2:
                log.warning("%s -> %s; retry %d/%d in %.0fs", url, reason, attempt + 1, self.max_attempts, delay)
            time.sleep(delay)
        self.stats["failed"] += 1
        raise RuntimeError(f"gave up after {self.max_attempts} attempts: {url}")

    def download_day(self, sym: str, day: date, side: str, dest_dir: Path) -> str:
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / raw_file_name(sym, day, side)
        if path.exists():
            self.stats["cached"] += 1
            return "cached"
        try:
            blob = self.fetch(day_url(sym, day, side))
        except RuntimeError as exc:
            log.error("%s", exc)
            return "failed"
        tmp = path.with_suffix(".part")
        tmp.write_bytes(blob or b"")
        tmp.replace(path)
        key = "ok" if blob else "404"
        self.stats[key] += 1
        return key

    def download_range(
        self,
        sym: str,
        start: date,
        end: date,
        dest_dir: Path,
        sides: tuple[str, ...] = SIDES,
        skip_saturday: bool = True,
        progress_every: int = 50,
    ) -> dict[str, int]:
        """Download every day in [start, end] for the given sides. Resumable."""
        counts = {"ok": 0, "cached": 0, "404": 0, "failed": 0}
        day = start
        done = 0
        while day <= end:
            if not (skip_saturday and day.weekday() == 5):
                for side in sides:
                    counts[self.download_day(sym, day, side, dest_dir)] += 1
                    done += 1
                    if done % progress_every == 0:
                        log.info("%s %s: %d files (%s)", sym, day, done, counts)
            day += timedelta(days=1)
        return counts


def decode_bytes(blob: bytes, sym: str, day: date) -> pl.DataFrame | None:
    """Decode one day file into a frame with columns ts, o, h, l, c, v (UTC, filler minutes dropped)."""
    if not blob:
        return None
    raw = lzma.decompress(blob)
    if not raw:
        return None
    rec = np.frombuffer(raw, dtype=CANDLE_DTYPE)
    scale = price_scale(sym)
    o = rec["o"].astype(np.float64) / scale
    h = rec["h"].astype(np.float64) / scale
    l = rec["l"].astype(np.float64) / scale
    c = rec["c"].astype(np.float64) / scale
    v = rec["v"].astype(np.float64)
    keep = ~((v == 0) & (o == c) & (o == h) & (o == l))
    if not keep.any():
        return None
    day_start = np.datetime64(datetime(day.year, day.month, day.day), "us")
    ts = day_start + rec["t"].astype(np.int64).astype("timedelta64[s]").astype("timedelta64[us]")
    df = pl.DataFrame({"ts": ts[keep], "o": o[keep], "h": h[keep], "l": l[keep], "c": c[keep], "v": v[keep]})
    return df.with_columns(pl.col("ts").dt.replace_time_zone("UTC"))


def decode_file(path: Path) -> pl.DataFrame | None:
    """Decode a raw file named {SYM}_{YYYYMMDD}_{SIDE}.bi5. Zero-byte files yield None."""
    if path.stat().st_size == 0:
        return None
    sym, day, _side = parse_raw_file_name(path.name)
    return decode_bytes(path.read_bytes(), sym, day)
