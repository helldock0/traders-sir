# AlphaBasketAssistant.mq5 v1.01: pre-live review (2026-10-14)

Reviewed: `D:\Traders sir\mt5\AlphaBasketAssistant.mq5` (1019 lines), read-only. Checked against the spec in the review
request, the reference engine (`reference/gj-strat/gjstrat/engine.py`, `patterns.py`), the terminal's own
`MQL5\Include\Trade\Trade.mqh`, and the backtest trade lists in `runs/basket/legs/*.parquet`. No source file was changed.
Not run in MT5: API behaviour was checked against the documentation and the Trade.mqh source; the overlap numbers in B2
come from the backtest trade lists (server day = 17:00 New York to 17:00 New York).

**Verdict: do not attach it to the live account yet.** 2 blockers, 8 majors, 12 minors.
The core mechanics are right: box window, ATR20 and median, CTrade calls, OCO in the normal case, break-even,
re-entry timing, date rules, StringFormat. The problems are restart state, a PLACE path with no checks of its own,
and the guard arithmetic.

Fix order:
1. B1 (a restart re-offers skipped box days; PLACE has no validation).
2. Decide B2 (the budget guard blocks most gotobi trades; the backtest odds assume they are taken).
3. M1 and M2 (guard formula, missing 10% budget).
4. M3 to M5 (one shared button, late clicks, half-placed OCO pair).
5. M6 to M8 (GTC leftovers, stop re-imposed, time exits), then the minors.

---

## Blockers

### B1 (blocker). After a full reload a skipped box day is offered as READY, and PLACE does no validation of its own
Lines: 128, 473-503, 530-534, 752, 760-766, 517-518, 596-628, 630-648.

Problem
- `g_boxSkip` (vol filter OFF, weekend, too few bars, flat or empty box) is not saved by SaveState and not rebuilt by
  LoadState. StartBoxDay runs only when `g_boxDay != g_todayUtc` (752), so after a reload on the same UTC day
  `g_boxSkip` is `""` and line 760 lets the state machine set ACT_BOX "READY" until 05:30.
  A reload is: terminal restart (VPS or Windows reboot, MT5 update), re-attaching the EA, loading a profile or
  template, recompiling, logging in to the account again. A timeframe change keeps globals and is not affected.
- PlaceBoxOrders and PlaceReentry trust the state machine completely: no check of `g_boxHi > g_boxLo`, `g_boxBars`,
  `g_volOn`, or a minimum stop distance.
- Effect 1: on a vol-OFF day (about half of all days) the panel shows "vol filter ... OFF" and "BOX READY" at the
  same time; one click trades a day the strategy skips.
- Effect 2: if the stored box is flat or 0/0 (BuildBox found no bars, 517-518), risk = spread only (0.2-0.5 pip).
  LotsForRisk returns roughly 8-19 lots (capped only by SYMBOL_VOLUME_MAX) and GuardsAllow passes, because the dollar
  risk is still 0.25%. `ask >= g_boxHi` is true, so a market BUY is sent with SL = the bid read a moment earlier.
  Usually rejected as invalid stops; if the bid ticked up first it is accepted, and slippage, not the stop, decides
  the loss on a position of that size.

Fix
1. Persist the skip reason (numeric code in a global variable, restored in LoadState), or re-derive it in OnInit when
   `g_boxDay == g_todayUtc` (D1 bars do not change between 00:30 and 05:30 UTC, so a recomputed `g_volOn` gives the
   00:30 answer).
2. Give PlaceBoxOrders and PlaceReentry their own gate: `g_boxDay == g_todayUtc`, `g_boxSkip == ""`,
   `IsWeekday(g_boxDay)`, `g_boxBars >= InpBoxMinBars`, `g_boxHi > g_boxLo`, `!InpVolFilter || g_volOn`, and
   `risk >= MathMax(3 * g_pip, 3 * (ask - bid))`.
3. Add a hard lot cap input (for example `InpMaxLots`) checked in every Place* function.

### B2 (blocker, spec-level: the code does what the spec says). The budget guard blocks most gotobi entries and many M-3 entries at full risk
Lines: 400-407 (with 361, 403, 404).

Problem
- Gotobi and M-3 risk 4%, and the budget limit is the same 4%. Any other open risk or any loss today makes
  `worst > 4`. One box trade on its original stop is enough: 3.99 + 0.25 = 4.24, BLOCKED.
- Measured on the backtest trade lists (`runs/basket/legs/*.parquet`): 87% of the 499 gotobi trades had a box position
  open at 00:55 UTC. Under the current formula at least 58% would certainly be blocked (the open box trade never
  reached break-even, or a box stop-loss or TP closed earlier the same server day); the true share is 58-89%. Even with
  the M1 formula at least 54% stay blocked (open box trade that never reached break-even). M-3: at least 36%, up to
  48% of 189 trades. The odds in `runs/basket/speed_report.md` and the README (28% pass within 60 days) assume these
  trades were taken; `scripts/basket_speed.py` models the firm's 5%/10% rules but not this entry guard.
- The current formula also blocks after a realised profit: lots are sized on `Balance()` (361) but `newPct` divides by
  the day-start (403), and today's profit is not credited (`MathMax(DailyUsedPct(), 0)`, 404). A box TP after server
  midnight (+2.25%) makes a 4% gotobi count as 4.09% of day-start: BLOCKED.
- Protect (risk halved below 97%) removes the conflict, so the gap is largest early in the challenge.

Fix (your decision before going live)
- Option a: keep the 4% entry guard (398) and give the budget its own limit just under the firm's 5% (new input, for
  example `InpBudgetPct = 4.6`), computed with the corrected formula in M1 plus a cost allowance (m8). Keeps the
  tested sizing.
- Option b: size gotobi and M-3 at 3.7% so they fit next to one box trade under 4% (`InpBudgetPct = 4.0`), then
  re-run the speed report.

---

## Majors

### M1 (major). Budget formula mixes equity with stop risk: floating losses counted twice, floating profits offset realised losses
Lines: 345, 374-392, 402-406.

Problem: `worst = max(DailyUsedPct, 0) + openPct + newPct`. `DailyUsedPct` is equity-based (it already contains the
floating P/L) and `openPct` is measured from the open price to the SL. A box trade 10 pips under water is counted as its
floating loss plus its full stop risk (too strict). Realised -1.5% today with two box trades floating +0.7% each
(stops not yet at break-even) is counted as 0.1% used instead of 1.5% (too lenient).

Fix: compare worst-case equity (every stop hit, no floating P/L) with both limits; keep lines 398-399 as they are.
```mql5
double WorstEquity(const double newRiskUsd, bool &unbounded)
  {
   unbounded = false;
   double eq = Balance();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i); if(t == 0) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), vol = PositionGetDouble(POSITION_VOLUME);
      if(sl <= 0) { unbounded = true; continue; }
      double mv = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? sl - op : op - sl;   // < 0 = loss at the stop
      double ts = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
      double tv = SymbolInfoDouble(sym, mv < 0 ? SYMBOL_TRADE_TICK_VALUE_LOSS : SYMBOL_TRADE_TICK_VALUE_PROFIT);
      if(ts > 0) eq += vol * mv / ts * tv + PositionGetDouble(POSITION_SWAP);
     }
   return eq - newRiskUsd;
  }
// in GuardsAllow, replacing 400-407 (costUsd: see m8)
bool unb; double wEq = WorstEquity(riskUsd + costUsd, unb);
double dWorst = 100.0 * (g_dayStart - wEq) / g_dayStart;
double mWorst = 100.0 * (InpAccountStart - wEq) / InpAccountStart;
if(unb || dWorst > InpBudgetPct || mWorst > InpMaxGuardPct)
  { why = StringFormat("budget: worst day %.2f%%, worst total %.2f%%", dWorst, mWorst); return false; }
```

### M2 (major). No max-loss budget: an allowed entry can break the static 10% limit
Lines: 399, 400-407.

Problem: the only total-loss check is `MaxUsedPct() >= 9` (399). Example: balance 9,150 (-8.5%), protect on, gotobi
2% = $183. Daily used 0, max used 8.5 < 9, budget 2.0 < 4: allowed. If it stops, equity is 8,967 = -10.3%: account
failed. Any protected 2% trade taken below about -8% (with costs) does this.

Fix: the `mWorst > InpMaxGuardPct` test in the M1 code.

### M3 (major). One PLACE button: an unclicked box or a pending re-entry hides the gotobi, and the panel says "window passed"
Lines: 765, 783, 793-794, 802-803, 880-882, 891-893, 995-1006.

Problem: the gotobi and M-3 actions are set only if `g_action == ACT_NONE` (793, 802). ACT_BOX stays active until 05:30
if the box was not clicked (765), ACT_REENTRY until 05:30 (783). If at 00:55 the box is still unclicked, or a re-entry
is ready (trade 1 stopped 00:30-00:49), or that re-entry is BLOCKED (red button), the whole 00:55-01:05 gotobi window
passes without the gotobi being offered, and the GOTOBI line reads "window passed" (882) during the window. The click
also executes whatever Update() recomputes at click time (998-1004), which can differ from the label just read.

Fix: compute the box/re-entry signal and the gotobi/M-3 signal separately and give each its own PLACE and skip button
(or give the timed market leg priority during its 10-minute window). Store the action drawn on each button and in
OnChartEvent execute only if the recomputed action equals it. Show "waiting behind box signal" instead of
"window passed" in that case.

### M4 (major). Late clicks create trades the backtest never had
Lines: 765, 609-618, 783, 641-644.

Problem: the spec's market fill applies at 00:30, and the engine places the re-entry exactly 6 minutes after the stop.
The EA keeps both clickable until 05:30. A click at 02:00 with the ask above the box high buys at market far above the
level (the engine filled at the level on the first touch, and may already have been stopped and re-entered). If price
touched a level and came back, a late click places fresh stops although the engine's trade 1 already happened. A late
re-entry click checks only the price at the click.

Fix: allow the market branch only within `InpSignalWindowMin` of 00:30. For any later click, scan the M1 bars from
00:30 (re-entry: from `reAt`) to now and refuse ("box already broken at HH:MM") if the bid high plus the current spread
reached `g_boxHi` or the bid low reached `g_boxLo` (re-entry: its level). A late click is then either equivalent to the
engine or refused.

### M5 (major). One side of the OCO pair can fail and is never retried
Lines: 619-626, 583-594 (prices read at 598).

Problem: `any = b || s` and `g_boxPlaced = true` even if one side failed. A buy stop is rejected (invalid price) when
the ask reaches the box high, or comes within SYMBOL_TRADE_STOPS_LEVEL of it, between the price read (598) and the
send. Then only the sell stop exists, the panel says "stop order(s) working", nothing offers the buy side again, and the
engine's action (market BUY, no sell stop) never happens; the lone sell stop can fill later after a reversal.

Fix: read SYMBOL_TRADE_STOPS_LEVEL and SYMBOL_TRADE_FREEZE_LEVEL first and treat `ask >= g_boxHi - stops * _Point` as
crossed (market entry on that side only, inside the 00:30 window); symmetric for the low. If exactly one side still
fails: re-read prices; if that level is now crossed, delete the other order and take the market entry; otherwise
delete the placed order, keep `g_boxPlaced = false` and log "box not placed, click again".

### M6 (major). GTC fallback: expiry depends on the EA running that same UTC day; a leftover order can fill on a later day without a click
Lines: 587-591, 759, 684-697, 976-977.

Problem
- 587-591 retry as GTC after any failure. CTrade already rejects an unsupported ORDER_TIME_SPECIFIED locally with
  TRADE_RETCODE_INVALID_EXPIRATION (Trade.mqh ExpirationCheck); other failures (price off, connection) also trigger
  the GTC retry, and a lost reply can leave two orders.
- The EA's own deletion (759) runs only inside `if(g_boxDay == g_todayUtc)`. If the terminal is off at 05:30 and comes
  back on a later day, nothing deletes the GTC order: before 00:30 the block is skipped, after 00:30 it compares with
  the new day's 05:30. The order can then fill with no click that day.
- When it fills it is treated as today's trade: AdjustBoxFill re-anchors its TP (and may tighten its SL) to today's
  `g_boxRisk`; the stop is never widened (`slOk`, 691, keeps a tighter SL), but break-even then follows the new TP,
  today's fresh OCO pair is deleted as "OCO sibling" (688), and it counts as today's trade 1 for the re-entry logic.

Fix
1. In PlaceStop retry as GTC only if `g_trade.ResultRetcode() == TRADE_RETCODE_INVALID_EXPIRATION`. Log
   SYMBOL_EXPIRATION_MODE in OnInit so you know whether ACG supports SPECIFIED.
2. Delete expired box orders independently of `g_boxDay`, on every Update and in OnInit:
```mql5
datetime setupUtc = ToUtc((datetime)OrderGetInteger(ORDER_TIME_SETUP));
datetime expUtc   = DateOf(setupUtc) + expSec;    // set up between 00:30 and 05:30 of its own box day
if(UtcNow() >= expUtc) g_trade.OrderDelete(t);
```
3. Put each order's own risk in its comment (for example `ABA-B1 b=0.2500 r=0.2530`, 24 chars) and use it in
   AdjustBoxFill instead of the global `g_boxRisk`.

### M7 (major). FixStopAfterFill re-imposes the gotobi/M-3 stop on every tick, undoing a stop the trader tightened
Lines: 725-734, 795, 804.

Problem: any SL more than a point away from `op +/- dist` is reset (732-733) on every tick of the entry day, and the TP
is forced to 0. Move a 4% gotobi stop to break-even and the EA moves it back within a second. The spec asks for one
adjustment after the fill.

Fix: only move a stop that is missing or looser than wanted, and keep the TP:
```mql5
bool looser = (type == POSITION_TYPE_BUY) ? (sl < want - g_point) : (sl > want + g_point);
if(sl <= 0 || looser)
   g_trade.PositionModify(t, NormalizeDouble(want, g_digits), PositionGetDouble(POSITION_TP));
```

### M8 (major). Time exits miss a leftover position until the next day's exit time, including over a weekend
Lines: 796, 805.

Problem: the exit fires only while today's UTC clock is past 06:00 (M-3: 12:00). If the terminal is off at 06:00 and
returns after UTC midnight, the gotobi short stays open until 06:00 that day. If Friday's exit is missed and the
terminal returns after the Friday close, the 4% position is held over the weekend and closed Monday 06:00, with a
"position close FAILED" log line every second on Saturday and Sunday after 06:00. Limiting the exit to positions
opened today would be wrong: a leftover would never be closed.

Fix: close each position at its own scheduled exit, so a leftover closes on the first tick after a restart (after a
weekend: at the Monday open) and a same-day position never closes early:
```mql5
datetime openUtc = ToUtc((datetime)PositionGetInteger(POSITION_TIME));
if(UtcNow() >= DateOf(openUtc) + exitSec) { /* close this ticket */ }
```

---

## Minors

- **m1 (minor). Box frozen at the first Update after 00:30 on the PC clock.** Lines 752, 513-515, 152.
  `TimeGMT()` follows the PC clock. If it runs fast, or the last 00:29 ticks are still in flight, the 00:29 bar is
  incomplete and the box is never rebuilt; a clock up to 6 minutes fast still gives at least 55 bars and passes.
  After a terminal start near 00:30, partly loaded M1/D1 history gives a permanent "only N bars" or "vol filter OFF"
  skip, or a vol decision on a short D1 series. (The backtest skipped any day with a missing box minute,
  `max_missing=0` in `engine.run`; the EA accepts up to 5.)
  Fix: start the box day only when `TimeCurrent() >= ToServer(g_todayUtc + placeSec)`, the last copied bar is the 00:29
  bar, and UpdateAtr received all `need` bars; otherwise show "waiting for data" and retry next second.
- **m2 (minor). CopyHigh/CopyLow counts can differ.** Lines 298-300. Both arrays are aligned at their newest element,
  so `n = MathMin(nh, nl)` indexed from 0 pairs highs and lows of different days.
  Fix: one CopyRates call, or require `nh == nl == need`.
- **m3 (minor). Short history.** Lines 303, 316. With fewer than 269 D1 bars the median uses fewer than 250 values and
  can turn the filter ON where the reference (`rolling(250, min_periods=250)`) gives NaN, i.e. OFF.
  Fix: if `InpVolFilter` and `cnt < InpMedianDays`, set `g_volOn = false`.
- **m4 (minor). Trade count is IN deals, not positions.** Lines 550-554, 563. A partly filled stop order (two IN
  deals, one position) counts as two trades: "done: two trades", no re-entry. DEAL_ENTRY_OUT_BY (Close By) is not
  treated as a close, so the day's state stalls.
  Fix: count distinct DEAL_POSITION_ID; accept OUT and OUT_BY.
- **m5 (minor). OCO deletion lives only inside AdjustBoxFill.** Lines 684, 688, 758, 769, 976-977. It is skipped when
  `g_boxRisk <= 0` (for example after lost global variables) and when the filled position is already closed by the time
  the event or poll runs (PositionByIdentifier returns 0 after a very fast stop-out). The sibling survives, line 769
  reports "stop order(s) working" and suppresses the re-entry branch, and the sibling can fill later with no 6-minute
  wait or price check.
  Fix: in OnTradeTransaction delete the sibling on any box IN deal before anything else; in Update delete any
  "ABA-B1" order whenever `g_bt.trades >= 1`.
- **m6 (minor). Time-exit closes carry the box magic.** Lines 464, 935, 1005. CTrade::PositionClose copies `m_magic`
  into the request (Trade.mqh line 500) and `g_trade` holds InpMagicBox. Gotobi/M-3 exit deals are tagged 241001, so
  OnTradeTransaction logs them as "exit box ... reason EA" and per-magic statistics are wrong.
  Fix: `g_trade.SetExpertMagicNumber(magic)` inside ClosePositions, restore afterwards.
- **m7 (minor). Working box stop orders are not in the budget.** Lines 374-392. The 00:30 pair becomes a 0.25%
  position later without any guard check.
  Fix: add the larger side's level-to-SL loss of working box orders to the open risk.
- **m8 (minor). Costs.** Lines 336, 403. DEAL_FEE is missing from the day-start sum; the budget ignores the new trade's
  commission and stop slippage. At 4% risk the cushion to the firm's 5% is 1%.
  Fix: add DEAL_FEE; add `lots x commission per lot + about 1 pip x lots` to the new risk in the guard (`costUsd`).
- **m9 (minor). Persistence.** Lines 473-503. Global variables reach disk only at terminal shutdown or on
  `GlobalVariablesFlush()`; a crash loses the day's flags. A lost `g_boxPlaced` re-offers the box (duplicate pair);
  a lost `g_boxRisk` disables the OCO (m5). Keys are not per account or symbol (demo and live in one terminal share
  them).
  Fix: `GlobalVariablesFlush()` at the end of SaveState; prefix keys with the account login and `_Symbol`; also treat
  the box as placed if a box-magic order was set up since today's 00:30 (HistoryOrdersTotal) or `g_bt.trades > 0`.
- **m10 (minor). Clock and logs.** Lines 843-844, 451-452, 464-465, 720, 796, 805. A server offset other than +2/+3 h
  only turns the header red; entries and time-based actions carry on with a wrong clock. Tickets are cast to int in
  logs (wrong above 2,147,483,647). Close and delete failures are logged every second.
  Fix: block entries when `!offOk`; log tickets with `IntegerToString((long)t)`; log a repeated failure at most once a
  minute per ticket.
- **m11 (minor). OnInit checks.** Lines 926-945, 309, 320. No check for a hedging account (on netting the three legs
  merge into one position), for the USDJPY symbol, for free margin (OrderCalcMargin: at prop leverage a 4% M-3 lot in a
  low-ATR month, e.g. ATR20 50 pips, is about 4.8 lots and may not fit), or that `InpAtrDays`, `InpMedianDays`,
  `InpBoxMinutes` are > 0 (zero gives a zero divide at 309 or an out-of-range read at 320).
  Fix: refuse to start, or warn, for each.
- **m12 (minor). "skip today" does nothing** when no signal is active (1008-1016), despite its label.
  Fix: show "no signal" and ignore the click, or implement a real skip of the next box.

---

## Checked and correct (no change needed)

- **ATR20 and median (294-322).** CopyHigh/CopyLow into dynamic non-series arrays are oldest-first; start position 1
  skips the forming D1 bar; `atr[cnt-1]` is the mean of the previous 20 daily ranges; the 250-value median includes
  today's ATR20. Same as the reference (`rolling(20).mean().shift(1)`, then `rolling(250).median()`). At 00:30/00:55
  UTC the current server D1 bar is the New York-close bar the backtest labels with that date (no Sunday bars on a
  UTC+2/+3 New York-close server).
- **Box window (508-523).** Start = previous UTC day 23:30, end 00:29; the CopyRates time-range call includes both
  ends (60 bars). The whole window sits inside one server day (01:30-02:29 or 02:30-03:29 server), so server midnight
  never splits it; on Monday it starts 1.5-2.5 h after the Sunday open. Saturday and Sunday are skipped as weekend.
- **Server/UTC.** ToServer for CopyRates, HistorySelect and the order expiry; DEAL_TIME converted with ToUtc; the
  day-start uses server midnight (17:00 New York, the backtest's day reset). ORDER_TIME_SPECIFIED expiry is passed in
  server time.
- **CTrade argument order.** BuyStop/SellStop(volume, price, symbol, sl, tp, type_time, expiration, comment),
  Buy/Sell(volume, symbol, price, sl, tp, comment), PositionModify(ticket, sl, tp), OrderDelete(ticket),
  PositionClose(ticket, deviation): all correct.
- **StringFormat.** Every call checked: argument counts and types match (no long into %d, no double into %s). No
  integer-division or datetime-arithmetic errors; globals are declared before use.
- **DailyUsedPct** sign (positive = loss). Day-start = balance minus today's realised P/L since server midnight, balance
  operations skipped (DEAL_FEE aside, m8).
- **LotsForRisk.** SYMBOL_TRADE_TICK_VALUE_LOSS per tick size, floored to the volume step; below the minimum it returns
  0 and nothing is sent.
- **Stops are never loosened by the box code.** AdjustBoxFill keeps a tighter SL (break-even) on both sides, rewrites
  only when the TP is off or the SL is missing, and even with a mismatched `g_boxRisk` can only tighten.
  ManageBoxPositions only tightens, triggers on bid for longs and ask for shorts, and takes each position's risk from
  its own TP and its box from its comment, so an overnight box trade keeps its own break-even when the next day's box
  starts. The moved stop is box/6 as in the engine (`be_plus / sl_pips` = 5/30 of `sl_dist` = box); BASKET.md's
  "1/6 of the SL distance" wording is looser than the engine.
- **Loops** that modify, close or delete either iterate downward or do not change the list.
- **Re-entry and done conditions (771-784)** match the engine: only after a stop-loss close (original or moved stop)
  before 05:30, 6-minute wait, none if close + 6 min >= 05:30, skipped and used up if price is already past the level,
  max 2 trades, done after a TP.
- **Date functions (168-212).** MakeDate with ZeroMemory gives 00:00; DaysInMonth leap rule correct; a gotobi date
  rolled back from a weekend cannot leave its month. A Python port gives Oct-Dec 2026 dates identical to BASKET.md's
  table, and Feb 2028 (leap year) is right.
- **No entry without a click.** Place* functions are reached only from a click on the PLACE button (995-1006); time
  exits use PositionClose, which only closes on a hedging account. The one exception is a leftover GTC order (M6).
- **Stops present.** Every entry sends its SL in the same request, and no EA modify ever sends SL = 0. Two box
  positions at once (an OCO race, or yesterday's trade plus today's) each keep the SL/TP of their own order;
  AdjustBoxFill touches only today's latest position and break-even is per position, so the single `g_boxRisk`
  cannot widen a stop.
- **Panel.** Objects are created once (ObjectFind), only text and colour change each second, the button state is
  reset on every redraw and on the click; nothing leaks.
- **Restart mid-day.** Positions, orders, today's trade count and the re-entry state are rebuilt from history; placed
  and dismissed flags come from global variables (gaps: B1 and m9).

## Confirm with ACG before going live
1. Daily-loss base: the EA uses the balance at 00:00 server time. If ACG uses the higher of balance and equity at
   00:00, an overnight box trade in profit makes every daily check too lenient.
2. USDJPY.pro settings: SYMBOL_EXPIRATION_MODE includes SPECIFIED (if not, M6 applies every day),
   SYMBOL_TRADE_STOPS_LEVEL (M5), leverage and margin (m11).
3. Turning Algo Trading off also stops the OCO cancel, break-even, time exits and expiry deletion; only the header
   turns red.
