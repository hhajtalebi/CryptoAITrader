# PR: v2.2.0 — Professional auto-trading terminal + full docs & release package

## Title

```
v2.2.0: Professional auto-trading terminal + full docs & release package
```

## Body

### ✨ What's new (v2.0 → v2.2 — Auto Trading page only, other pages untouched)

**v2.2.0 — Professional terminal (round 2, per user's issue list):**
- 📊 **Info cards**: 9 capital cards with icon + title + amount; daily PnL colored green/red by the data's own sign
- 📈 **Pro chart**: indicator menu (EMA 21 / SMA 50 / Bollinger Bands — computed by the shared indicators library on real candles), drawing tools (movable horizontal line, two-click trend line, clear-all), colored-icon symbol menu (custom delegate), one-click PNG snapshot, chart type (candles/line/area), zoom reset, candle refresh 15s → 5s, live price line per tick, entry/SL/TP lines
- 🤖 **AI opinion**: on-demand analysis by the existing autonomous agent on the chart's symbol/timeframe — direction, confidence, steps, reasoning (LLM explains, never invents numbers)
- 🔍 **Always-live opportunity scanner**: background watch scan (`scalp.watch_*` settings, default 20s) keeps the 17-column table alive even with the engine off; scanner settings modal; "enterable" = confidence ≥ threshold & spread within limit; real entry still passes all engine gates
- 📋 **Open positions**: 19th Action column with per-row Close button; symbol click opens full details modal with close button; sorting off for this live table (cell widgets don't follow Qt sort moves)
- ⭐ **Favorite symbols**: searchable checkable picker with icons → saves `scalp.selected_symbols` AND syncs DB watchlist (usable across dashboard/analysis/signals)

**v2.1.x — Terminal layout & real bug fixes:**
- Terminal-style layout: chart-dominant main row (5:2), bottom tabs "Opportunities (n) | Open Positions (n)" with live counts, single-row header, settings collapsed by default
- Fixed: symbol combo never populated (controller now calls `set_auto_symbols` in `_on_symbols_loaded`)
- Fixed: chart stayed empty forever if markets loaded late (bootstrap retries every tick)
- Qt traps fixed: `addItem` on empty combo silently sets index 0 (later `setCurrentIndex(0)` emits nothing); row-index kept in `Qt.UserRole` so clicks survive sorting

**v2.0 — Event-driven engine:**
- Scalping terminal + prediction dashboard, single Prediction Engine, 3 engine modes (Selected Symbols / Market Scan / AI Auto), trend ladder 4H→1m, millisecond tick-driven exits with poll fallback, STALE-data entry block, bid/ask/last separation, never-shrinking tables, responsive 1280×720→1920×1080, Margin≠Notional with 6 allocation modes, no mock data anywhere

### 📚 Docs
All docs updated for 2.2.0: README fa/en (trading page row + corrected counts: 11 pages, 84 test files / 2,270 tests), NEXT_TASK, docs/SCALP_FA (new Part 5), docs/HANDOVER_FA (stale 1.10.0 header → 2.2.0 real numbers), docs/PROFESSIONAL_ROADMAP_FA (honest status on items 2.2/2.3), docs/SIGNAL_TABLES_FA (v2.2 note), PROJECT_PROGRESS, AI_HANDOVER, BUILD_INFO. Version bumped in all six locations.

### 📦 Release package
`release/` folder for GitHub distribution: `CryptoAITrader-v2.2.0-2026-09-23.zip` (478 files), `SHA256SUMS.txt`, `RELEASE_NOTES_FA.md` (Polish Persian release notes).

### ✅ Tests
**2,269 passed + 1 skipped** (LSTM optional, needs torch) — full suite ~6 min. New: `tests/test_v22_terminal_pro.py` (19 tests). No mock data; all values from real engines.

### Scope guardrails honored
- Only the Auto Trading page + its internal dashboard; other pages untouched
- No new prediction engine — shared single source with the Prediction page
- Reference image used for layout/UX only — none of its numbers became mock data
- User settings never overwritten (new `scalp.watch_*` keys have defaults only)
