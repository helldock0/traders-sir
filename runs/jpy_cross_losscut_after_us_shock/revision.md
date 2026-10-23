# Pre-registration amendment (cycle 3, before any run)

Applied the Critic's 'revise' verdict: DST-aware NY cash window 09:30-16:00; shock_pct from the start level; k grid 0.75/1.0/1.5 -> 0.5/0.75/1.0; monotone kill restated; regime kill (check avg R > 0 with 2022 removed); expected design t 1.5 -> 1.0; cost 0.035 R -> 0.05-0.08 R.

Old grid: {"k": [0.75, 1.0, 1.5], "sl_atr": [0.5, 1.0], "exit_utc": ["02:00", "06:00"]}
Old pre_registered: {"expected_design_t_min": 1.5, "expected_avg_r": 0.1, "min_trades_design_per_market": 40, "kill_if": "Stage A best design avg R on AUDJPY <= 0 or design t < 1; or avg R does not rise with k (no monotone response to shock size across 0.75 / 1.0 / 1.5 at the same stop and exit), which would mean the sign is noise rather than a size-triggered liquidation; or NZDJPY and CADJPY both negative in stage B while AUDJPY is positive (then it is one market's luck, not a retail-book effect). Sample is small in design (the US100 feed covers 2013-2017 cleanly, about 45-70 Monday-Thursday shock days at k = 1.0), so a design t between 1 and 2 with a positive check and walk-forward is the realistic good outcome; a design t >= 2 is the hoped-for one."}
