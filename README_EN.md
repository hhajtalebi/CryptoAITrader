# Crypto AI Trader

**Professional desktop app for crypto market analysis and futures signal generation**

Version 1.0.0 · Windows 10/11 · Python 3.12+ · Persian & English

[راهنمای فارسی](README.md)

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

- Keys are stored in the **Windows Credential Manager** via `keyring`.
- If no OS keyring is available, they go into an **encrypted file** outside the database.
- Keys are **never** written to SQLite, source code, or log files — a dedicated filter masks anything key-shaped before it reaches a log.
- Backups **never contain secrets** (there is an automated test for this).

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
│   ├── pages/               7 pages
│   ├── charts/              Candlestick chart
│   └── controllers/         Wires the UI to the engines
├── migrations/              Alembic migrations
├── tests/                   92 tests
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

92 tests covering indicators, risk engine, signal engine, AI response validation, timeframes, localization, backup, reporting, and async execution.

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
