"""Run one strategy on one or more markets and print the split table.

    uv run python scripts/run_backtest.py strategies/oracle/m3_usd_bid.py --symbols USDJPY --tf M1
    uv run python scripts/run_backtest.py strategies/oracle/m3_usd_bid.py --symbols EURUSD --tf M1 --params '{"side":"SELL"}'
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer  # noqa: E402

from edge.engine.backtest import backtest, load_strategy  # noqa: E402
from edge.engine.costs import CostModel  # noqa: E402
from edge.engine.stats import format_split_table  # noqa: E402

app = typer.Typer(add_completion=False)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def main(
    strategy: str = typer.Argument(..., help="path to a strategy .py file or a dotted module"),
    symbols: str = typer.Option("USDJPY", help="comma list"),
    tf: str = typer.Option("M1"),
    params: str = typer.Option("{}", help="JSON overrides for PARAMS"),
    start: str = typer.Option(None),
    end: str = typer.Option(None),
    no_swap: bool = typer.Option(False),
    commission: float = typer.Option(7.0, help="USD per lot round turn (FX)"),
    slippage: float = typer.Option(0.2, help="pips on market and stop fills (FX)"),
    be_trigger_r: float = typer.Option(0.0),
    be_lock_r: float = typer.Option(0.0),
    trail_r: float = typer.Option(0.0),
    save_trades: str = typer.Option(None, help="write trades to this parquet/csv path"),
) -> None:
    mod = load_strategy(strategy)
    p = json.loads(params) if params else {}
    costs = CostModel(commission_per_lot_usd=commission, slippage_pips=slippage, include_swap=not no_swap)
    for sym in [s.strip().upper() for s in symbols.split(",") if s.strip()]:
        t0 = time.time()
        res = backtest(mod, sym, tf, p, costs, start, end, be_trigger_r=be_trigger_r, be_lock_r=be_lock_r, trail_r=trail_r)
        print(f"\n## {res.strategy} on {sym} {tf}  params={res.params}  ({res.notes['bars']:,} bars, {time.time() - t0:.1f}s, "
              f"ask modelled {100 * res.notes['ask_modelled_share']:.1f}%)")
        print(format_split_table(res.stats))
        print("R by year:", {y: round(v, 1) for y, v in res.by_year.items()})
        reasons = res.trades.group_by("reason").len().sort("reason") if res.trades.height else None
        if reasons is not None:
            print("exits:", dict(zip(reasons["reason"], reasons["len"])))
            print(f"avg comm_r {res.trades['comm_r'].mean():.4f}  avg swap_r {res.trades['swap_r'].mean():.4f}  "
                  f"avg spread at entry {res.trades['spread_entry'].mean():.5f}  avg bars held {res.trades['bars_held'].mean():.1f}")
        print("passes bar:", res.passes_bar)
        if save_trades:
            out = Path(save_trades)
            if out.suffix == ".csv":
                res.trades.write_csv(out)
            else:
                res.trades.write_parquet(out)
            print("trades ->", out)


if __name__ == "__main__":
    app()
