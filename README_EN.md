# Crypto AI Trader

**Professional desktop app for crypto market analysis and futures signal generation**

Version 2.5.4 · Windows 10/11 · Python 3.11+ (tested up to 3.13) · Persian & English

[راهنمای فارسی](README.md)

> **Current delivery 2.5.4:** the app no longer closes by itself after hours (background task handles leaked
> and the trade monitor wrote to the database hundreds of times a second); logs, crash traces and a session
> heartbeat now go to `data\logs\`. Auto trading really opens trades and shows why candidates were rejected.
> New **⚡ Ultra scalp** (paper, live prices): whole-market momentum scan every second, close at your net profit
> after fees, up to 200 concurrent trades. [Release report](docs/RELEASE_2.5.4_FA.md).
>
> **Previous delivery 2.5.3:** build robots fixed — the Windows installer build no longer opens app windows
> (full tests are opt-in with `--with-tests` and run headless) and streams its output to `build_logs\`; the APK
> build checks the WSL toolchain, installs buildozer into a venv, builds on the Linux filesystem and ships the
> missing icon/presplash/font assets. [Release report](docs/RELEASE_2.5.3_FA.md).
>
> **Previous delivery 2.5.2:** LBank futures HTTP 403 (Cloudflare firewall) — browser-like headers, the exact
> Cloudflare block code and reason in the wallet report, no retries of rejected requests, and a fix hint.
> [Release report](docs/RELEASE_2.5.2_FA.md).
>
> **Previous delivery 2.5.1:** the wallet shows assets again (LBank signature headers, fallback
> balance endpoints, a sync report with the cause and fix of any error, auto-sync every 60 s); the
> watchlist really saves and can be built from a right-click menu on any market row; markets are ordered
> by market cap and volume (BTC, ETH first) with exact USDT prices. [Release report](docs/RELEASE_2.5.1_FA.md).
>
> **Previous delivery 2.5.0:** share signals (Telegram, WhatsApp, X, email, Rubika/Eitaa/Bale), a
> stretched rounded search bar, "Act on this trade" with the calculator's entry/SL/TP1–3 and staged exits
> (⅓ at TP1 + stop to entry, ⅓ at TP2, rest at TP3), a rebuilt trade-history table, a prefilled position
> calculator, a three-tab wallet (Overview/Spot/Futures) with the LBank futures balance fixed, and a paper
> balance that mirrors the real wallet. [Release report](docs/RELEASE_2.5.0_FA.md).
>
> **Previous delivery 2.4.2:** heavy scan computation now runs in a separate low-priority
> worker process (the UI no longer freezes), the performance page refreshes lazily and off
> the UI thread, repeated scans stop re-saving the same signal, a stall watchdog logs any UI
> freeze, and you can copy a signal's symbol or full info from the tables and the details
> dialog. [Release report](docs/RELEASE_2.4.2_FA.md).
>
> **Previous delivery 2.4.1:** fixes the heavy load / freezes during whole-market scans:
> scans no longer write candles to disk or flood the shared cache, CPU share is capped,
> the network loop stays responsive, indicators are ~45% faster and the results table is
> light. [Release report](docs/RELEASE_2.4.1_FA.md).
>
> **Previous delivery 2.4.0:** Signals → Scan can cover the top symbols by turnover
> (manual count, as before) or the **whole exchange**, with a smart filter, a minimum
> 24h turnover, live results and an ETA. Automatic signals get a selectable source —
> signals found above, the whole market, or both — and the full rotation covers every
> exchange symbol. [Release report](docs/RELEASE_2.4.0_FA.md).
>
> **Previous delivery 2.3.2:** LBank connectivity — WebSocket now uses the official
> `wss://api.lbank.info/ws/V2/` with fallback domains, client pings and proxy fallback;
> LBank error 10004 ("request too frequent") is treated as a rate limit with a short
> cooldown instead of an authentication failure. [Release report](docs/RELEASE_2.3.2_FA.md).
>
> **Previous delivery 2.3.1:** fixes "online for a few seconds, then disconnected"
> (excess REST polling triggered exchange rate limits), honours 429/418 with a global
> cooldown, treats fresh REST *or* WebSocket data as online, and adds a professional
> dashboard command center. [Release report](docs/RELEASE_2.3.1_FA.md).
>
> **Previous delivery 2.3.0:** independent exit monitoring, serialized entries and
> single-flight exits, net fee accounting, two same-provider streams with fresh REST
> fallback, rotating liquid-market/favorite scans, and opportunity entry → open history
> with details and explicit close actions. **758 passed / 4 skipped** in the selected
> subset; native Qt/Windows behavior remains unverified. Profit, zero losses and uptime
> are not guaranteed. [Release report](docs/RELEASE_2.3.0_FA.md). Source only; no commit/push.

> **Previous delivery 2.2.2:** fixes prediction cache updates, complete trading
> settings propagation and backup sensitivity metadata (encrypted keys retained).
> Adds a separate local download portal. **708 passed / 3 skipped** in the core
> subset; full desktop/Windows testing remains unverified. See
> [release notes and download server instructions](docs/RELEASE_2.2.2_FA.md).
> The 2.2.1 note below is historical. No commit or push has been made.

> **2.2.1 review/documentation delivery (2026-09-23):** no application logic changes.
> See the [project memory](docs/PROJECT_MEMORY_FA.md), [complete static code index](docs/CODE_MAP.md)
> and [validation/open findings](docs/REVIEW_VALIDATION_FA.md) (Persian).
> Some historical descriptions below are stale: there are 5 registered strategies and 14
> timeframe codes; certain AI paths change decisions/levels; data defaults to the application
> directory, and encrypted secrets can be present in the database and its backups.
> This review ran 674 passing tests and 2 skips in a non-UI subset, not the historical full-suite
> result. Full collection was blocked by missing Qt system libraries. This is a source delivery,
> not a newly built executable. Commit/push require the owner's explicit permission.

---

## ⚠ Read this first

This is an **analysis tool**, not financial advice and not a trading bot.

- It places no orders and has no access to any trading account. **Version 1 does no real trading.**
- A signal's "confidence" is **not a probability of profit**. It only measures how many analytical factors agree with each other. 80% confidence means the indicators align — not that 80% of such trades win.
- Every trading decision is entirely your own responsibility.

---

## What it does

| Feature | Description |
|---|---|
| **Live market data** | REST + WebSocket with auto-reconnect and a working offline mode |
| **13 timeframes** | 1m to 1w; timeframes the exchange doesn't serve are aggregated from lower ones automatically |
| **24 indicators** | Trend, momentum, volatility, volume, and support/resistance |
| **Signal engine** | `LONG` / `SHORT` / `WAIT` with entry, stop loss, three targets, R/R, and suggested leverage |
| **Risk engine** | Structural or ATR-based stops, stop-distance clamping, rejection of low-quality setups |
| **AI analysis (optional)** | Multi-timeframe narrative from a local model (Ollama) or any OpenAI-compatible endpoint |
| **Predictive intelligence (new in 2.0)** | A 13-horizon ladder (1m to 7d) with probability distributions (P10…P90), market regimes, scenarios, and accuracy scored against real prices |
| **Reports** | CSV, Excel, JSON, PDF, and HTML export |
| **Backup** | Manual backups plus automatic ones before every migration, with restore |
| **Bilingual** | Persian (RTL) and English (LTR), switchable at runtime |

---

## Quick start

### Option 1 — Executable

Run `CryptoAITrader.exe` from the `dist` folder. No Python installation needed.

### Option 2 — From source

```bash
git clone <repository-url>
cd CryptoAITrader

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
python main.py
```

### Building the Windows executable

```bat
scripts\build_windows.bat
```

Output lands in `dist\CryptoAITrader\CryptoAITrader.exe`.

---

## First run

A **welcome wizard** asks for:

1. Language and theme (dark, light, or follow Windows)
2. Exchange — defaults to **LBank**, which needs **no API key** for public market data
3. AI analysis — **off by default**; the app is fully functional without any paid service
4. Risk parameters — notional account balance, risk per trade, and max leverage

Your settings are stored in the database and are **never overwritten by defaults or upgrades**.

---

## Run modes

```bash
python main.py                      # GUI
python main.py --check              # Health check, no window
python main.py --signal BTC/USDT    # Generate one signal on the command line
python main.py --log-level DEBUG    # Verbose logging
```

---

## The pages

| Page | Purpose |
|---|---|
| **Dashboard** | Connection status, watchlist overview, latest signals |
| **Markets** | Full market list with search and watchlist. Double-click a row to analyse that symbol |
| **Analysis** | Candlestick chart with volume, moving averages, key levels, indicator table, AI narrative |
| **Signals** | Multi-timeframe signal generation and full history |
| **Predictions** | The predictive intelligence report: horizons, regimes, scenarios, warnings, what changed, and recorded accuracy |
| **Trading** | Professional auto-trading terminal: 9 icon-topped capital cards, live candlestick chart (1m–4h) with EMA/SMA/Bollinger overlays, drawing tools, PNG snapshot and icon-based symbol menu; prediction panel with on-demand AI analysis; always-live 17-column opportunity scanner (runs even with the engine off) with modal settings; 19-column open positions with per-row Close button and details modal; 10-cell risk panel; favorite symbols via searchable checkable picker stored in the database |
| **Reports** | Build a report over a date range and export it in five formats |
| **Settings** | Language, theme, exchange, AI, risk parameters, backup and restore |
| **Help** | Concept explanations and FAQ |

---

## How a signal is built

```
Multi-timeframe candles  →  24 indicators  →  3 strategies vote
                                                  ↓
                              votes weighted by timeframe
                              (1m: 0.3  …  1w: 2.0)
                                                  ↓
                            |score| ≥ 0.22  →  LONG or SHORT
                            otherwise       →  WAIT
                                                  ↓
                  Risk engine checks stop distance, R/R, leverage
                  Setup rejected  →  WAIT with a stated reason
                                                  ↓
              (optional) AI adds narrative text only —
                     it never changes any price
```

**`WAIT` is a real, useful answer.** Most of the time the market has no clean setup and the app deliberately declines to invent one. An app that always has a signal is guessing.

---

## Optional AI analysis

The app is fully functional without AI. To enable it:

**1. Local model (free, recommended)**

```bash
# Install Ollama from ollama.com
ollama pull llama3.1
ollama serve
```

Then in Settings: provider = `local`, model = `llama3.1`.

**2. OpenAI-compatible service** — enter the base URL and API key in Settings.

**3. Custom provider** — see [`docs/ADD_AI_PROVIDER_FA.md`](docs/ADD_AI_PROVIDER_FA.md).

The AI **cannot invent data**. It reaches real market data only through defined tools, and must return `INSUFFICIENT_DATA` when data is missing. Its output is validated before display.

---

## API key security

- SecretStore supports OS keyring, encrypted-file and encrypted-database backends. With the default `security.store_secrets_in_db=True`, Application selects the **encrypted database backend**.
- Raw keys must not be written to source or logs. Logging/error filters redact sensitive values; encrypted ciphertext in SQLite is not the same as storing plaintext keys.
- File/database key derivation is not equivalent to OS-backed DPAPI protection; improving it remains an open security-review item.
- Database backups **can contain encrypted secrets**. Version 2.2.2 marks these snapshots as sensitive in the manifest without deleting keys. OS keyring data and `.secret_store.bin` are not included. Keep all personal backups private.

---

## Project layout

```
CryptoAITrader/
├── main.py                  Entry point
├── app/                     Core: config, database, security, logging, DI
│   └── application.py       The only place components are wired together
├── market/                  Market data
│   └── providers/lbank/     LBank implementation (swappable)
├── indicators/              24 indicators
├── signals/                 Signal engine, risk engine, strategies
├── ai/                      AI agent, providers, prompts
├── reports/                 Report building and export
├── backup/                  Backup and restore
├── localization/{fa,en}/    Translations
├── ui/                      GUI
│   ├── pages/               11 pages
│   ├── charts/              Candlestick chart
│   └── controllers/         Wires the UI to the engines
├── migrations/              Alembic migrations
├── tests/                   84 test files (2,270 tests)
├── scripts/                 Build and run scripts
└── docs/                    Documentation
```

---

## Documentation

| Document | Topic |
|---|---|
| [`docs/ADD_EXCHANGE_FA.md`](docs/ADD_EXCHANGE_FA.md) | Adding a new exchange |
| [`docs/ADD_INDICATOR_FA.md`](docs/ADD_INDICATOR_FA.md) | Adding a new indicator |
| [`docs/ADD_AI_PROVIDER_FA.md`](docs/ADD_AI_PROVIDER_FA.md) | Adding an AI provider |
| [`docs/LBANK_API_FA.md`](docs/LBANK_API_FA.md) | LBank API details |
| [`docs/DATABASE_FA.md`](docs/DATABASE_FA.md) | Database schema and migrations |
| [`docs/ARCHITECTURE_FA.md`](docs/ARCHITECTURE_FA.md) | Architecture and design decisions |
| [`docs/TROUBLESHOOTING_FA.md`](docs/TROUBLESHOOTING_FA.md) | Common problems |

Documentation is written in Persian, matching the project's primary audience. Code identifiers, filenames, and this README are English.

---

## Tests

```bash
scripts/run_tests.sh          # Linux/macOS
python -m pytest tests -q     # Windows
```

2,270 tests across 84 files covering indicators, risk engine, signal engine, AI response validation, timeframes, localization, backup, reporting, async execution, and the auto-trading terminal.

---

## Where your data lives

```
%LOCALAPPDATA%\CryptoAITrader\        (Windows)
~/.local/share/CryptoAITrader/        (Linux)
├── crypto_ai_trader.db    Database
├── backups/               Backups
├── exports/               Exported reports
└── logs/                  Log files
```

Set the `CAT_DATA_DIR` environment variable to relocate it.

---

## License

Provided as-is, without warranty of any kind. Using it means accepting full responsibility for your own trading decisions.
