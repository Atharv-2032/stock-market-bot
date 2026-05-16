from database.db import get_session, init_db, Signal, Trader
from datetime import datetime, timezone
from utils.logger import logger
import json

init_db()
session = get_session()

# check if AFL trader exists in leaderboard
trader = session.query(Trader).filter(Trader.ticker == "AFL").first()
if trader:
    logger.info(f"Found AFL trader: {trader.id}")
    trader_id = trader.id
else:
    logger.warning("AFL not on leaderboard — using placeholder")
    trader_id = "insider_AFL_test"

# insert test signal
signal = Signal(
    trader_id=trader_id,
    ticker="AFL",
    signal_type="insider_filing",
    direction="BULLISH",
    size=500000.0,
    price_at_signal=100.0,
    source="sec_rss",
    raw_data=json.dumps({
        "title": "4 - AFL insider purchase",
        "company": "Aflac Inc",
        "trade_date": "2026-05-08",
        "insider_count": 1
    }),
    timestamp=datetime.now(timezone.utc),
    processed=0
)
session.add(signal)
session.commit()
logger.info(f"Test signal inserted with id: {signal.id}")
session.close()