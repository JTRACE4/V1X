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

UPDATE 3 (same day) - patch on top of the streak tile (nothing reset; streak + history carry on)
- WALL MOVED vs PULLED: a big Coinbase wall that disappears and re-appears within 2s on the same side at +/-15% size is
  logged as "WALL MOVED UP/DOWN ($old -> $new)" - repeat moves of the same wall update ONE alert with a move count.
  Only a wall that is never re-quoted is "PULLED / SPOOF", and only if it sat within 0.15% of price when it vanished.
- Live price + line crosses use the CF Benchmarks spot constituents only (Coinbase, Kraken, Bitstamp, Gemini; LMAX if a
  feed is added). Perps keep feeding the buy-pressure bar but can never fake a line cross.
- Final minute: PROJECTED SETTLEMENT (the running 60-second average Kalshi settles on) under the target, plus the average
  the remaining seconds need to flip it (LOCKED when that is 0.25%+ away from live price).
- Kraken: judged on its own WebSocket trade ticks only (taker b/s side, rolling buffer, de-duplicated) - no longer compared
  with Kraken's 24h ticker snapshot, which caused the false "Kraken looks off" math-check warning.
- WIN RATE badge top-right (sits in the empty corner on phones): current streak, all-time win %, today's record.
  Tap it for full round history: BTC / XRP, sealed / early / bot call, today / this week / all-time, day-by-day (60 days)
  and week-by-week (52 weeks) tables, and every graded round 300 at a time. Read from the saved history file
  (data_cache/kalshi_dashboard_history.json, up to 50,000 rounds) - the same one the streak tile uses.

UPDATE 4 (same day)
- ROUND HISTORY SAFETY NET: Railway wipes data_cache on every redeploy unless a volume is mounted, which erased the
  round history + streak on each code push. Now every browser that opens the dashboard keeps a full backup (IndexedDB)
  and pushes back any rounds the server lost - automatically, a few seconds after the page loads. A yellow banner shows
  while history is not on a volume. Permanent fix (2 minutes): Railway -> service -> Settings -> Volumes -> mount at /data,
  then Variables -> DATA_DIR=/data.
- FLIP RADAR rebuilt: no longer mirrors Kalshi's price. 0-99% composite flip risk for the call on screen from
  opposing 10s/30s/1m taker flow (+ net dollars while price moves at the line), cushion to the line + line crosses,
  every exchange's bid/ask walls, market pace, and the final-minute 60s settlement average. LOW / WATCH / HIGH / CRITICAL
  with the exact drivers listed. Kalshi's number is shown underneath as a reference only.
- REVERSAL CALLS: the early / sealed call now goes to the LOSING side when the flip score of the current favorite is 55%+
  and at least 3 of (RSI stretched 68+/32-, 58%+ of short-window flow against, candles turning, trend against, price
  moving at the line) agree - RSI required unless 4+ agree. Shown as "REVERSAL ~4.5x" with the Kalshi payout, graded like
  every call, and tracked separately in the round history (record, avg payout, units won/lost). The bot's own real-money
  auto-buy is unchanged - reversal calls never place a trade on their own.

UPDATE 5 (same day)
- FLIP RADAR 10-SECOND RULE: the score shown is the lowest reading of the last 10 seconds, so a 1-2 second burst can't
  throw it from 15% to 45%. Pressure has to hold 10 straight seconds to lift it above 20%; it drops straight away when
  pressure eases. A one-off burst is shown underneath as "burst to N% right now - counts only if it holds 10s".
  Reversal calls use the same steadied score.
- BACKTEST (backtest_engine.py): runs on the server 90s after start and again every 24h. Pulls the last 21 days of settled
  KXBTC15M rounds from Kalshi (strike, result, price every minute), Coinbase 1-minute prices and Binance 1-minute taker
  volume, rebuilds the 4:00 and 8:00 reads, and grades: buying the favorite, the current call rules (by tier), reversal
  calls (with a threshold sweep) and a search for filters that win 80%+ - chosen on the older 70% of rounds, checked on
  the newest 30% they never saw. Win rate AND money (Kalshi price + 1c slippage + fee). Report: /backtest
  (also /backtest.txt, /backtest.json, /backtest_run to re-run now).
- Live effect: reversal calls switch off for a stage whose reversals lost money in the backtest; calls matching a filter
  that held 80%+ on unseen rounds get a "★ 80% SETUP" tag showing its backtest win rate and money result.
