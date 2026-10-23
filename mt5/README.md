# Alpha Basket Assistant (MT5)

Semi-automatic assistant for the USDJPY basket on the Alpha Capital Group (ACG) MT5 account. It never opens a trade
by itself: it computes each setup at its clock time, sizes the lot, shows the dashboard and waits for your click.
After the click it manages the trade (OCO cancel, stop and target from the fill, break-even, time exits, expiry) and
blocks new entries when the loss guards are hit. This is the design ACG's help centre allows for EAs (risk
management and trade assistance, pre-approved); EAs that open trades on their own are refused.

Source: `mt5/AlphaBasketAssistant.mq5`. Compiled copy: ACG terminal data folder, `MQL5\Experts\AlphaBasketAssistant.ex5`.
Log of every signal, click, fill and exit: `MQL5\Files\ABA_log.csv` in the same data folder.

## Legs (times UTC; IST = UTC + 5:30)

| Leg | When | Trade | Stop | Exit | Risk |
|---|---|---|---|---|---|
| Box | box 23:30-00:29, orders at 00:30, expire 05:30 | buy stop at the box high + sell stop at the box low (OCO) | box + spread | TP 9R; at +3R stop to entry + box/6; overnight allowed | 0.25% |
| Gotobi | 5/10/15/20/25/month-end (weekend -> Friday), 00:55 | SELL at market | 0.25 x ATR20 | 06:00 | 3.6% |
| M-3 | 3rd-last weekday of the month, 11:00 | BUY at market | 0.25 x ATR20 | 12:00 | 3.6% |

Why 3.6% and not 4%: the entry budget (below) blocks a trade whose stop, added to the open box risk and costs, would
exceed 4.6% of the day-start balance. At 4% that blocked a quarter to two thirds of the gotobi trades in the backtest;
at 3.6% almost none are blocked and the cushion under the firm's 5% stays the same.

Box and gotobi only when ATR20 >= its 250-day median (the dashboard shows ON/OFF). After a box stop-out before
05:30, six minutes later the panel offers one re-entry stop on the other side at the original box level (max 2
trades a day, done after a take profit).

## Install (once)

1. Open ACG Markets MT5, press F4 (MetaEditor) only if you want to read the source; the .ex5 is already compiled.
2. In MT5: View > Navigator > Expert Advisors > drag `AlphaBasketAssistant` onto a USDJPY.pro chart (any timeframe, M5 is fine).
3. In the inputs: set `InpAccountStart` to the account's starting balance (10000) and `InpTargetPct` to 10 for phase 1 (5 for phase 2). Leave the rest.
4. Tick "Allow Algo Trading" in the EA dialog and make sure the toolbar button "Algo Trading" is green. The panel's top line turns red if it is off.
5. Check the panel's first line: it shows UTC time and the server offset (+2 or +3 h). If it says "CHECK PC CLOCK", fix the Windows clock before trading.
6. Keep the terminal running on this PC (or a VPS) during 23:30-06:00 UTC and 11:00-12:00 UTC.

## Daily routine

| UTC | IST | You |
|---|---|---|
| 00:30 | 06:00 | Panel says BOX READY -> click PLACE (or skip). Orders then work until 05:30 UTC. |
| 00:55 | 06:25 | Gotobi days with vol ON: panel says SELL GOTOBI -> click within 10 minutes. Closes itself at 06:00 UTC. |
| after a box stop-out | | Six minutes later the panel may say RE-ENTRY READY -> click or skip. |
| 11:00 | 16:30 | 3rd-last weekday: panel says BUY M-3 -> click within 10 minutes. Closes itself at 12:00 UTC. |

The button turns red with the reason when a guard blocks an entry (daily loss used, max loss used, budget, AutoTrading off).

## Guards (defaults, v1.02)

- Daily: entries blocked once today's loss including open P/L reaches 4% of the day-start balance (firm limit 5%).
- Max: entries blocked once the account is down 9% from the start (firm limit 10%).
- Budget: before every entry the EA computes the equity if every stop hits (open positions at their stops, the
  larger side of a working box pair, the new trade plus $7 per lot commission and 1 pip of slippage). The entry is
  blocked if that equity would be more than 4.6% below the day-start balance or more than 9% below the start.
  With gotobi at 4% and one box trade at its original stop that is 4.25% plus costs, so it passes; a second
  4% trade the same day does not.
- Lot cap: 5 lots per order (`InpMaxLots`).
- Protect: all risk halved while the balance is below 97% of the start (switch off with `InpProtect = false`).
- Clock: if the PC clock disagrees with the server by anything other than 2 or 3 hours, entries are blocked.
- Two button rows: the top one is the box (place / skip), the bottom one is the timed leg of the day (gotobi or
  M-3). A click only acts if the signal is still the one the button showed.

## Things the EA cannot know (confirm with ACG)

1. Whether the daily loss is measured from the balance at 00:00 server time or from the higher of balance and
   equity. The EA uses the balance; if ACG uses the higher one, keep box trades small overnight.
2. Turning Algo Trading off also stops the OCO cancel, break-even, time exits and expiry deletion: the header turns
   red. Do not switch it off while a basket trade is open.
3. Whether a pending stop order with an expiration time is accepted on `USDJPY.pro` (the Journal shows a warning at
   start if not; the EA then deletes expired orders itself at 05:30 UTC while it is running).

## ACG approval

Email the `.ex5` file to ACG support for pre-approval before using it on the account, describing it as a
trade-assistance and risk-management tool: it only places orders after a manual click, and manages stops,
break-even, time exits and loss limits. Keep the reply.

## Odds (backtest, 2018-2025 starts, Alpha Swing rules with open P/L counted in the daily loss, entry budget modelled)

| Mix (box / gotobi / M-3) | pass within 60 days | lose the account within 60 days | pass eventually | months per funded account |
|---|---|---|---|---|
| 0.25 / 3.6 / 3.6 (EA default) | 24.5% | 9.9% | 67% | 7.8 |
| 0.25 / 4 / 4 | 25.5% | 14.3% | 58% | 7.9 |
| 0.25 / 3 / 3 | 20.0% | 7.4% | 79% | 7.9 |

The 3.6% mix keeps the 60-day odds of the 4% mix at two thirds of its ruin rate. Computed with
`edge.engine.prop.simulate(..., budget_pct=4.6)`; the wider study without the budget is `runs/basket/speed_report.md`.
