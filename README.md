# Multi-Agent Quantitative Trading System

A fully automated algorithmic trading pipeline for US equities, built in Python. Four autonomous agents work in sequence to discover insider trading signals and unusual options flow, evaluate them with GPT-4o, and execute trades — currently running in observe mode to validate strategy quality before going live.

---

## How It Works

```
Scout (every 4 hrs)
  └── Discovers and scores traders from SEC EDGAR, Finviz, S&P 500 options
  └── Maintains a leaderboard of top 20 traders by Sharpe ratio

Watchdog (every 3 mins, market hours only)
  └── Monitors 3 signal channels: insider filings, insider purchases, unusual options
  └── Scans full S&P 500 (~500 tickers) for unusual options flow
  └── Deduplicates signals — one per ticker per 24 hours

Analyst (triggered by Watchdog)
  └── Filter 1: Price staleness — skips signals where price has moved >5%
  └── Filter 2: Conviction — options ratio and insider trade size vs daily volume
  └── Filter 3: Market impact — skips illiquid stocks
  └── Filter 4: Signal count — requires minimum confirmation
  └── GPT-4o classification → TRADE / WATCH / SKIP

Executor (triggered by Analyst; position monitor every 30s)
  └── Priority ranking — insider signals > high LLM score > high conviction
  └── Re-analyses each signal fresh before executing (prevents stale trades)
  └── Risk guards: daily loss limit, max open positions
  └── Tracks stop loss (3%) and take profit (5%) on all open positions
```

All four agents communicate exclusively through a SQLite database. If any agent crashes, the others keep running.

---

## Signal Sources

| Source | Type | Universe |
|--------|------|----------|
| SEC EDGAR Form 4 | Insider filing | Leaderboard tickers |
| Finviz insider buys | Insider purchase | Leaderboard tickers |
| yfinance options | Unusual options flow | Full S&P 500 (~500 tickers) |

---

## Tech Stack

```
Python 3.12
SQLite + SQLAlchemy    — persistent storage across restarts
APScheduler            — job scheduling
yfinance               — price data and options flow
SEC EDGAR API          — insider filing detection
BeautifulSoup          — Finviz scraping
OpenAI GPT-4o          — signal classification
loguru                 — structured logging
```

---

## Project Structure

```
stockmarket_bot/
├── agents/
│   ├── scout.py          # Trader discovery and leaderboard management
│   ├── watchdog.py       # Signal detection across 3 channels
│   ├── analyst.py        # 4-filter pipeline + GPT-4o classification
│   └── executor.py       # Trade execution, position monitoring, P&L tracking
├── core/
│   ├── stocks.py         # yfinance price wrapper
│   ├── sec.py            # SEC EDGAR API wrapper
│   ├── options.py        # S&P 500 options scanner
│   ├── portfolio.py      # Finviz insider scraper
│   ├── scoring.py        # Sharpe, win rate, ROI calculation
│   ├── risk.py           # Position sizing, stop loss, market impact
│   └── llm.py            # GPT-4o signal classification
├── database/
│   └── db.py             # SQLAlchemy models: Signal, Verdict, Trade, Position, Trader
├── utils/
│   ├── config.py         # Config loader
│   └── logger.py         # Loguru setup
├── main.py               # APScheduler entry point
└── config.yaml           # All tunable parameters
```

---

## Configuration

All parameters live in `config.yaml`:

```yaml
scout:
  run_interval_hours: 4
  min_sharpe: 0.3
  top_n_traders: 20

watchdog:
  poll_interval_seconds: 180
  unusual_options_volume_threshold: 1.5

analyst:
  max_price_drift: 0.05
  min_signals_required: 1
  min_options_ratio: 1.5

executor:
  execution_mode: observe      # observe → paper → live
  budget_per_trade: 100
  max_open_positions: 20
  stop_loss_pct: 0.03
  take_profit_pct: 0.05
```

---

## Execution Modes

The system supports three modes, switchable via `config.yaml` with no code changes:

| Mode | Description |
|------|-------------|
| `observe` | Simulates trades, records to DB, tracks hypothetical P&L |
| `paper` | Places real orders on Alpaca paper trading account |
| `live` | Places real orders with real capital |

---

## Setup

**Prerequisites:** Python 3.12+, OpenAI API key, (optional) Alpaca API keys for paper/live trading.

```bash
git clone https://github.com/YOURUSERNAME/stockmarket_bot.git
cd stockmarket_bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_key_here
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_key_here
```

Run the system:

```bash
# foreground
python main.py

# background (recommended for overnight runs)
nohup python main.py > logs/main.log 2>&1 &
echo $! > main.pid
```

Check logs:

```bash
tail -f logs/main.log
```

Stop:

```bash
kill $(cat main.pid)
```

---

## Monitoring

Check open positions and P&L at any time:

```bash
python3 -c "
from database.db import get_session, init_db, Position, Trade
init_db()
s = get_session()
positions = s.query(Position).all()
print(f'Open positions: {len(positions)}')
for p in positions:
    pnl = (p.current_price - p.entry_price) / p.entry_price * p.size
    print(f'  {p.ticker} | entry:\${p.entry_price:.2f} | current:\${p.current_price:.2f} | PnL:\${pnl:.2f}')
closed = s.query(Trade).filter_by(status=\"closed\").all()
print(f'Closed: {len(closed)} | Realised PnL: \${sum(t.pnl for t in closed):.2f}')
s.close()
"
```

A P&L report also runs automatically every 2 hours in the logs.

---

## Early Results (Observe Mode)

After the first week of observe mode testing:

```
Closed trades:    4
Win rate:         100%
Realised PnL:     $28.82  (on $100/trade budget)
Unrealised PnL:   $14.98
Total PnL:        $43.81
Notable trade:    INTC — entry $107.15, exit $117.12 (+9.3%)
```

Statistical validity requires 50+ closed trades. These early results are encouraging but not conclusive.

---

## Design Decisions

**Why insider signals AND options flow?**
Insider filings are high-conviction but infrequent. Unusual options flow is frequent but noisier. Running both in parallel maximises signal coverage — the Analyst filters quality.

**Why re-analyse before execution?**
Signals can sit in the queue for hours before a position slot opens. Re-running all 4 filters at execution time ensures stale signals (price moved, market closed) are discarded before a trade is placed.

**Why leaderboard-only for insider signals but S&P 500 for options?**
Insider signals carry legal and reputational weight — we only follow traders with a proven historical track record. Options flow is anonymous; casting the full S&P 500 net maximises detection.

**Why 3%/5% stop loss/take profit?**
Chosen specifically for the testing phase — tighter thresholds mean faster trade cycling and more data accumulated per week. Will be tuned once 50+ trades are closed.

---

## Roadmap

- [x] Scout agent — trader discovery and scoring
- [x] Watchdog agent — 3-channel signal detection
- [x] Analyst agent — 4-filter + GPT-4o pipeline
- [x] Executor agent — priority ranking, risk guards, position monitoring
- [x] Chained pipeline — Watchdog → Analyst → Executor
- [x] Market hours gating — pipeline only runs during US market hours
- [x] Automated P&L reporting
- [x] AWS EC2 deployment — continuous 24/7 operation
- [ ] Alpaca paper trading integration
- [ ] Frontend dashboard for strategy monitoring

---

## Disclaimer

This system is for research and educational purposes. It is not financial advice. Past performance in observe mode does not guarantee future results in live trading. Always validate a strategy thoroughly before deploying real capital.
