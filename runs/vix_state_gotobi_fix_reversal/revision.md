# Pre-registration amendment (cycle 10, before any run)

Applied the Critic's 'revise' verdict (R1-R7) in full before building:
- R1 common sample: every arm, 'all' included, trades only gotobi weekdays from 2011 on which both the ATR median and the VIX percentile are defined.
- R2 one threshold: vix_pct 50 only (trailing 250-close median, the ATR rule's construction); V+ / V- are strict complements; the 70 cells and the 'pct <= 100 - vix_pct' arm are dropped.
- R3 hypothesis cell: the spec grid and the only cell stages B/C validate is {state: ['atr_or_vix'], vix_pct: [50]} (ATR-high or VIX-high), minimum 300 design trades.
- R4 stage A grid of nine cells at vix_pct 50: all, atr, atr_vix, atr_vixlo, natr_vix, natr_vixlo, atr_or_vix, and the non-gotobi placebo ng_vix / ng_vixlo; reference and placebo arms are never promoted.
- R5 kill rule K1-K5 (stratified VIX effect E >= +0.10 R in design with both strata positive; union design t above the 'atr' arm's and natr_vix above natr_vixlo; gotobi effect above the placebo effect by +0.05 R; E > 0 in check and union check t at least the 'atr' arm's; E reported gross and net with month-clustered SEs).
- R6 expectations restated: union 3.8 trades a month, E between 0 and +0.10 R, union score 0.27-0.33 if E > 0; a null means 'no VIX effect larger than about 0.2 R on the gotobi'.
- R7 mechanism restated as risk appetite and front-run inventory; a VIX-low result is never registered as a low-vol hypothesis.

Old pre_registered: {"expected_design_t_min": 2.0, "expected_avg_r": 0.2, "min_trades_design_per_market": 90, "expected_trades_per_month": 1.5, "kill_if": "In design on USDJPY, read from every stage A cell in research.sqlite: the best vix_hi cell (by design t) does not exceed the 'all' arm by at least +0.05 R, or atr_vix does not exceed 'atr' by at least +0.05 R at the same vix_pct, or vix_lo is at least as good as vix_hi at the same vix_pct, or the best vix cell has fewer than 90 design trades. Reference arms are never promoted and a vix_lo > vix_hi result is never registered as a low-vol hypothesis. Speed: the approved vol-gotobi scores about 0.3 (0.17 R on 2.6 trades a month); this tests whether implied vol raises the leg's quality, not whether it reaches 0.7."}

Files amended: runs/<slug>/hypothesis.json, specs/auto/<slug>.json (grid, stage_a.grid, params, notes, pre_registered, rationale), the DB spec_json, and the builder brief (regenerated with the Critic's notes).
