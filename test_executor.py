from database.db import get_session, init_db, Signal, Verdict, Trader
from datetime import datetime, timezone
from utils.logger import logger
import json

init_db()
session = get_session()

# find a trader on leaderboard
trader = session.query(Trader).first()
if not trader:
    logger.error("No traders on leaderboard — run Scout first")
    session.close()
    exit()

logger.info(f"Using trader: {trader.name} | ticker: {trader.ticker}")

# insert test signal
signal = Signal(
    trader_id=trader.id,
    ticker=trader.ticker,
    signal_type="insider_filing",
    direction="BULLISH",
    size=1000000.0,
    price_at_signal=50.0,
    source="sec_edgar",
    raw_data=json.dumps({
        "title": f"Test insider purchase — {trader.ticker}",
        "company": trader.name,
        "trade_date": "2026-05-14",
        "insider_count": 1
    }),
    timestamp=datetime.now(timezone.utc),
    processed=1  # already processed by analyst
)
session.add(signal)
session.flush()

logger.info(f"Test signal inserted — id: {signal.id}")

# insert TRADE verdict for this signal
verdict = Verdict(
    signal_id=signal.id,
    verdict="TRADE",
    staleness_score=0.02,
    conviction_score=0.15,
    signal_count=2,
    safe_size=5000.0,
    llm_score=0.75,
    llm_reasoning="Insider with strong track record buying ahead of earnings | risk: LOW",
    timestamp=datetime.now(timezone.utc)
)
session.add(verdict)
session.commit()

logger.info(f"Test TRADE verdict inserted — id: {verdict.id}")
logger.info(f"Ticker: {trader.ticker} | conviction: 0.15 | llm: 0.75")
session.close()