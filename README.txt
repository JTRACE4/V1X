KALSHI DASHBOARD - FLAT VERSION (every file in ONE folder, no subfolders)

GITHUB / RAILWAY: upload ALL the files in this folder to the top level of the repo (delete the old ones first).
  Railway starts it with the Procfile:   web: python kalshi_web_dashboard.py
  It listens on Railway's PORT automatically. Logs / history folders (bot_state, data_cache) are created by the app itself.
WINDOWS: double-click "Start Dashboard.bat"  (or:  python kalshi_web_dashboard.py  then open http://127.0.0.1:8765)
OPTIONAL: Cryptometer context - add a file named cryptometer_key.txt containing your key (or a CRYPTOMETER_API_KEY variable on Railway).

UPGRADE 2026-10-20 - what changed
- Order flow rebuilt aggr.trade-style (src/orderflow_engine.py): every exchange trade is counted ONCE (exchange trade-id de-dupe;
  reconnect replays are dropped and counted on screen). Fills of one market order are added back into one "print".
- New venues: Binance futures, BitMEX, Bitget futures (silently drop out if your region blocks them).
- Liquidations streamed (Binance futures, Bybit, OKX, BitMEX, Deribit) - shown separately, never added to volume.
- Bookmap-style liquidity tracker on the full Coinbase book: big walls EATEN vs PULLED.
- Optional Cryptometer context: put your API key in a file named cryptometer_key.txt in this folder. Context only, never added to totals.
- BTC BOUGHT vs SOLD bar: BTC + dollars, 10s/30s/1m/5m/this round, spot vs perps, net volume delta chart, biggest market orders.
- Vertical BUY PRESSURE & VOLUME bar uses the same de-duplicated numbers.
- EARLY call locks at 4:00, SEALED call locks at 8:00 (never changes). Both graded vs Kalshi's real result with their own track record.
  The bot's own auto-buy calls are unchanged (shown in one line under the header).
- Top strip: RSI FLIP METER (1m + 5m RSI, overbought/oversold, flip-risk score), FLIP METER (chance the sealed call flips),
  WHALE & LIQUIDITY ALERT box (whale prints, book sweeps, multi-exchange sweeps, stop-run sweeps of the high/low, liquidation cascades,
  walls pulled/eaten, BOOM moves) with sounds + voice. Test buttons are under "Sound & alert settings".

UPDATE 2 (same day)
- Chill night theme. Kalshi knight removed (Kalshi's UP/DOWN cents now sit under the live price).
- Big call boxes: EARLY call at 4:00 and SEALED call at 8:00, each with confidence SUPER / GOOD / WEAK.
  SUPER = 80%+ sure, GOOD = 65%+, WEAK = 55%+. The SEALED call only seals at GOOD or SUPER.
  A call is SKIPPED when it is basically 50/50 (under 55%), when price has crossed the line 3+ times this round,
  or when the round's range is under 0.025% (not enough price action). Exactly 2 crosses lowers it one level.
- "Line crosses this round" counter (UP / DOWN crosses) + chart at the bottom: this round live + the last 6 rounds,
  dots on every cross, 4:00 / 8:00 marks, result and call check marks. First start backfills from your existing log.
- Chart patterns: AMD (accumulation-manipulation-distribution) added; bull/bear flags and cup-with-handle now also
  show the confirmed BREAKOUT; rising / falling wedges unchanged (already detected, with breakout confirmation).
