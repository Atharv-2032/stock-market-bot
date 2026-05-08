from utils.logger import logger
from utils.config import load_config


# ─── Test 1 — Config ──────────────────────────────────────────
logger.info("Test 1 — Config")
config = load_config()
logger.info(f"Config loaded — execution mode: {config['executor']['execution_mode']}")
logger.info(f"Min sharpe: {config['scout']['min_sharpe']}")

# ─── Test 2 — Stocks ──────────────────────────────────────────
logger.info("Test 2 — Stocks (yfinance)")
from core.stocks import get_stock_price, get_return_after_date, get_average_daily_volume
from datetime import datetime, timedelta

price = get_stock_price("AAPL")
logger.info(f"AAPL current price: {price}")

past_date = datetime.now() - timedelta(days=60)
ret = get_return_after_date("AAPL", past_date, days=30)
logger.info(f"AAPL return 60 days ago over 30 days: {ret}")

vol = get_average_daily_volume("AAPL")
logger.info(f"AAPL avg daily volume: {vol}")

# ─── Test 3 — SEC EDGAR ───────────────────────────────────────
logger.info("Test 3 — SEC EDGAR")
from core.sec import get_recent_form4_fillings, get_form4_rss_feed, extract_ticker_from_filing, get_ticker_from_cik

filings = get_recent_form4_fillings(days_back=3)
logger.info(f"Form 4 filings last 3 days: {len(filings)}")

if filings:
    first = filings[0]
    source = first.get("_source", {})
    display_names = source.get("display_names", [])
    ciks = source.get("ciks", [])
    file_date = source.get("file_date", "")

    insider_name = display_names[0].split("(")[0].strip() if display_names else ""
    company_name = display_names[-1].split("(")[0].strip() if len(display_names) > 1 else ""
    company_cik = ciks[-1] if len(ciks) > 1 else ciks[0] if ciks else ""

    logger.info(f"Insider name: {insider_name}")
    logger.info(f"Company name: {company_name}")
    logger.info(f"Company CIK: {company_cik}")
    logger.info(f"File date: {file_date}")

    ticker = get_ticker_from_cik(company_cik)
    logger.info(f"Ticker: {ticker}")

rss = get_form4_rss_feed()
logger.info(f"RSS feed filings: {len(rss)}")
if rss:
    logger.info(f"First RSS entry: {rss[0]}")

# ─── Test 4 — Options ─────────────────────────────────────────
logger.info("Test 4 — Options (yfinance)")
from core.options import get_options_chain, get_unusual_options_activity, filter_significant_options

chain = get_options_chain("AAPL")
if chain:
    logger.info(f"AAPL options chain — expiry: {chain['expiry']}")
    logger.info(f"Calls rows: {len(chain['calls'])}")
    logger.info(f"Puts rows: {len(chain['puts'])}")
else:
    logger.warning("No options chain returned for AAPL")

activities = get_unusual_options_activity(["AAPL", "NVDA", "MSFT"])
logger.info(f"Total options records: {len(activities)}")

significant = filter_significant_options(activities, min_volume=100, min_ratio=1.5)
logger.info(f"Significant options signals: {len(significant)}")

# ─── Test 5 — Portfolio ───────────────────────────────────────
logger.info("Test 5 — Portfolio (OpenInsider)")
from core.portfolio import get_top_traders_from_openinsider

trades = get_top_traders_from_openinsider()
logger.info(f"OpenInsider trades: {len(trades)}")
if trades:
    logger.info(f"First trade: {trades[0]}")

# ─── Test 6 — Scoring ─────────────────────────────────────────
logger.info("Test 6 — Scoring")
from core.scoring import calculate_sharpe, calculate_win_rate, calculate_roi, score_insider

dummy_returns = [0.15, -0.05, 0.20, 0.08, -0.03, 0.12, 0.18, -0.02]
sharpe = calculate_sharpe(dummy_returns)
win_rate = calculate_win_rate(dummy_returns)
roi = calculate_roi(dummy_returns)
logger.info(f"Dummy returns sharpe: {sharpe}")
logger.info(f"Dummy returns win_rate: {win_rate}")
logger.info(f"Dummy returns roi: {roi}")

# ─── Test 7 — Database ────────────────────────────────────────
logger.info("Test 7 — Database")
from database.db import init_db, get_session, CandidateTrader
from datetime import timezone

init_db()
session = get_session()
dummy = CandidateTrader(
    id="test_AAPL_001",
    name="Test Trader",
    source="test",
    ticker="AAPL",
    sharpe=1.5,
    win_rate=0.65,
    roi=0.12,
    total_signals=10,
    avg_return=0.08,
    last_seen=datetime.now(timezone.utc),
    times_seen=1,
    status="candidate"
)
session.add(dummy)
session.commit()
result = session.query(CandidateTrader).filter_by(id="test_AAPL_001").first()
logger.info(f"DB write/read — trader: {result.name} | sharpe: {result.sharpe}")
session.delete(result)
session.commit()
session.close()
logger.info("DB test passed — dummy record cleaned up")

logger.info("All core tests complete")