# AlphaBasketAssistant.mq5 v1.02: re-review against review_v101.md (2026-10-14)

Reviewed: `D:\Traders sir\mt5\AlphaBasketAssistant.mq5` v1.02 (1191 lines), read-only, against every finding in
`review_v101.md`. The B2 numbers were recomputed on `runs/basket/legs/*.parquet` with the v1.02 budget formula
($7/lot commission, 1 pip slippage allowance, 5-lot cap, $10k). No source file was changed.

**Verdict.** The code findings are fixed: B1, M1-M8 and 11 of the 12 minors are fixed, m10 is partly fixed, and
nothing regressed. The rewrite adds 6 new minor defects, none blocking. One item still needs your decision before
going live: B2. At 4% gotobi/M-3 risk the new 4.6% budget (with its cost allowance) still blocks at least 27% (up to
67%) of the backtest's gotobi trades and 16-38% of its M-3 trades.

Next action: decide B2 (gotobi and M-3 at 3.6% brings the blocked share to 0-10% and 1-4%), then fix N1-N4.

---

## Status of the v1.01 findings

| ID | Status | v1.02 lines | Note |
|---|---|---|---|
| B1 | fixed | 98, 138, 550, 560, 566-577, 606-627, 689-699, 732, 776, 394 | Skip code persisted and restored. BoxPreflight gates both Place paths (box day, skip code, weekday, bars, hi > lo, vol filter, stop >= max(3 pips, 3 spreads)). InpMaxLots caps every order. A degenerate box can no longer be traded. |
| B2 | partly fixed | 41-45, 383, 403-441, 443-462 | Option a implemented as described, but at 4% risk it still blocks a large share. See the B2 section. |
| M1 | fixed | 403-441, 451-457 | Worst-case equity = balance + P/L at every stop incl. swap (no floating P/L, locked profit not credited) - larger working box order - new trade - costs. |
| M2 | fixed | 455, 457 | `mWorst > InpMaxGuardPct`. The -8.5% example (balance 9,150, 2% gotobi) is now blocked at 10.5% at the stops. |
| M3 | fixed | 127-129, 303-306, 953-954, 962, 1048-1050, 1071-1076, 1161-1182 | Separate rows; the gotobi no longer waits for the box action; a PLACE click acts only if the recomputed action equals the drawn one; "window passed" only after the window. Skip clicks lack that check (N3). |
| M4 | fixed | 735-741, 780, 676-686 | Late box click refused if a level was touched since 00:30 or price is past the box after the window; re-entry refused (and used up) if its level was touched since reAt. Touches inside the first 10 minutes are not checked (accepted: the stop then fills at the same level as the engine's). Residuals: N1, N2. |
| M5 | fixed | 737-738, 746-763 | Stops-level crossing tested before sending; one-sided failure goes to market on a crossed side or deletes the placed side and asks for a new click. |
| M6 | fixed | 704-715, 507-523, 911, 743, 784, 837, 863 | GTC only on INVALID_EXPIRATION; every box order deleted at 05:30 of its own setup day on every update; per-order r=/b= in the comment. An order can still fill while the EA is not running (inherent; the README says so). |
| M7 | fixed | 880-893 | Only a missing or looser stop is moved; the TP is kept. |
| M8 | fixed | 525-539, 956, 965 | Exit per position from its own open date; a leftover closes on the first tick after a restart (after a weekend: at the Monday open). |
| m1 | fixed | 590-603, 606-615, 61-62 | Waits for the server clock (TimeCurrent), the 00:29 bar and the full D1 history, up to 10 minutes; 60 bars required, as in the backtest. |
| m2 | fixed | 322-324 | One CopyRates call. |
| m3 | fixed | 345 | Filter OFF until 250 ATR values exist. Trivial: the panel (1024) and the data check (613) say 270 bars, the filter needs 269. |
| m4 | fixed | 635-650, 659, 1145 | Distinct DEAL_POSITION_ID count; OUT_BY accepted. |
| m5 | fixed | 824-828, 918, 1138-1139 | Runs on every update and on each box IN deal, no longer depends on g_boxRisk or on the position still being open. It now relies on the comment tag (N4). |
| m6 | fixed | 534, 537 | Magic set for each time-exit close. |
| m7 | fixed | 429-438 | Larger side of the working box orders, with costs. |
| m8 | fixed | 360, 383, 436, 439 | DEAL_FEE added; commission and slippage allowance for the new trade and working orders. Open positions' exit commission and stop slippage are still not counted (small). |
| m9 | fixed | 544-555, 1088, 920 | GlobalVariablesFlush, per-login/symbol keys, placed flag inferred from orders and fills. Gotobi/M-3 "taken" stay flags only (a duplicate would be blocked by the budget). Side effect of the inference: N5. |
| m10 | partly fixed | 447, 173, 239-245, 507-539 | Entries blocked on an offset mismatch, tickets logged as long, failure logs rate-limited. Still open: (1) the offset check catches a wrong time zone, not a wrong clock: TimeGMT and TimeTradeServer both follow the PC clock, so a clock that is minutes off keeps `g_offOk` true while the gotobi/M-3 windows, late-click timing, re-entry timing, stale-order deletion and time exits all shift by the error; (2) DeleteStaleBoxOrders and ClosePositionsByTime still run when `g_offOk` is false; (3) LogFail shares one timer (N6). Fix: treat `MathAbs(TimeTradeServer() - TimeCurrent()) > 60` while USDJPY is ticking as a clock error (block entries, Alert), and skip the stale deletion while the clock is in doubt. |
| m11 | fixed | 1092-1098, 458-460 | Hedging account required, numeric inputs checked, symbol and expiration-mode warnings, OrderCalcMargin check. |
| m12 | fixed | 1073, 1075 | Skip buttons show "-" with no signal. |

Regressed: none. The OCO now deletes by comment tag instead of "every box order", a robustness trade-off listed as N4.

---

## B2 (partly fixed): what remains

Problem
- The budget passes a 4% gotobi next to one box trade only if the gotobi lot is at most about 2.4-2.6 lots:
  4.00 + lots x ($7 + 1 pip) + 0.25 (box position) or about 0.27 (working box pair with its costs) must stay <= 4.6.
  That is a gotobi stop of at least about 23-25 pips (ATR20 >= about 94-100 pips). Two box trades on their original
  stops block it almost always. M-3 alone is blocked when its stop is under about 14 pips (lot above about 4.4):
  3% of the backtest's M-3 trades.
- On a vol-ON gotobi day the box pair is working, or a box trade is open, at 00:55 almost every time (both legs use
  the same filter).
- Recomputed on the backtest trade lists with the v1.02 formula: gotobi still blocked in at least 27% (up to 67%) of
  499 trades; M-3 in 16-38% of 189 (v1.01: 58-89% and 36-48%).
- The README sentence "4.25% plus costs, so it passes" holds only for lots up to about 2.5. The README's odds (28% pass
  within 60 days) still come from `scripts/basket_speed.py`, which does not model this guard.

| gotobi/M-3 risk | budget | gotobi blocked | M-3 blocked |
|---|---|---|---|
| 4.0% (v1.02 default) | 4.6% | 27-67% | 16-38% |
| 4.0% | 4.8% | 3-31% | 5-16% |
| 3.75% | 4.6% | 2-28% | 4-12% |
| 3.6% | 4.6% | 0-10% | 1-4% |
| 3.5% | 4.6% | 0-6% | 0-4% |

Lower bound: only box trades that never reached break-even, realised box losses since server midnight, and a working
box pair. Upper bound: every open box trade still on its original stop.

Fix (your decision)
- Set `InpRiskGotobi` and `InpRiskM3` to 3.6% (the 4.6% budget then leaves 0.4% under the firm's 5% beyond the
  modelled costs), or keep 4% and accept the blocked share.
- Either way, add the guard to `scripts/basket_speed.py` and re-run before relying on the pass odds.
- Raising the budget to 4.8% instead leaves only 0.2% beyond the modelled 1-pip slippage.

---

## New defects in v1.02 (all minor)

### N1 (minor). Refusals that every click will hit are not shown on the button
Lines: 926, 944, 1002, 1031, 740-741, 780.

Problem: after the 10-minute window, once a level has been touched since 00:30 (or price is past the box), every box
click is refused, yet the BOX button stays green "PLACE BOX STOP ORDERS ... until 05:30" and the status says READY.
A re-entry whose level was touched since reAt also shows green, and the click silently uses it up.

Fix: run the same late/touch checks in Update (or ButtonLabel) and end the action with a status such as
"box broken at HH:MM before placement, skipped" or "re-entry level touched at HH:MM".

### N2 (minor). Touch detection uses bid bars only, and the re-entry scan may skip the minute containing reAt
Lines: 676-686, 780.

Problem: a buy stop triggers on the ask, but `rates[i].high >= g_boxHi` tests the bid high, so an ask touch within one
spread below the level is missed. The re-entry scan starts at `ToServer(g_reAt)`, which is not minute-aligned
(close + 6 min), so the M1 bar containing reAt can be excluded.

Fix: for the high side test `rates[i].high + MathMax(rates[i].spread * _Point, Spread()) >= g_boxHi`; start the
re-entry scan at `g_reAt - g_reAt % 60`.

### N3 (minor). Skip clicks do not check the drawn action
Lines: 1170-1175, 1183-1187.

Problem: PLACE clicks act only if the recomputed action equals the drawn one; skip clicks act on whatever Update()
recomputes. A click on a "-" skip button in the second a signal appears dismisses that signal for the day.

Fix: apply the same `g_actBox == shownBox` / `g_actTimed == shownTimed` test before a skip.

### N4 (minor). OCO cleanup now depends on the order comment tag
Lines: 824-828, 488-505.

Problem: CleanupSiblings deletes only orders whose comment contains "ABA-B1" or "ABA-B2". If the server rewrites
pending-order comments, the sibling is never deleted and can fill until 05:30 (v1.01 deleted every box-magic order
once today's position was open). AdjustBoxFill and break-even fall back safely when r=/b= are missing; the OCO does
not.

Fix: when `g_bt.trades >= 1` and no re-entry has been placed, delete every box-magic order regardless of comment;
store the re-entry order's ticket (persisted) and keep only that one afterwards. On demo, check that the Trade tab's
Comment column shows "ABA-B1 b=... r=...".

### N5 (minor). The placed-flag inference counts any box order, including an old one that failed to delete
Lines: 920 (with 508-523).

Problem: CountBoxOrders() counts every box-magic order on the symbol. If an old order is still there when today's box
day starts (its deletion failed, for example AutoTrading off at that moment), today's box is marked placed and saved,
and it is never offered, even after the old order is gone.

Fix: count only orders with `ORDER_TIME_SETUP >= ToServer(g_boxDay + placeSec)`.

### N6 (minor). LogFail shares one timer across all failure types
Lines: 239-245.

Problem: after any logged failure, a different failure within the next minute (for example a time-exit close failing
just after an order delete failed) reaches only the panel's last line, not the log file.

Fix: rate-limit per event name and ticket, not globally.

---

## Confirm before going live
1. ACG's daily-loss base: the balance at 00:00 server time (as coded) or the higher of balance and equity.
2. USDJPY.pro: SYMBOL_EXPIRATION_MODE (the init log now prints it), SYMBOL_TRADE_STOPS_LEVEL, and the real
   commission per lot (`InpCommissionPerLot = 7` drives the budget).
3. Pending-order comments are preserved by the server (N4).
