from core.options import get_unusual_options_activity, filter_significant_options
from database.db import get_session, Trader
from utils.logger import logger

session = get_session()
traders = session.query(Trader).all()
tickers = [t.ticker for t in traders if t.ticker]
session.close()

logger.info(f"Tracked tickers: {tickers}")

activities = get_unusual_options_activity(tickers=tickers)
logger.info(f"Total options records: {len(activities)}")

if activities:
    # show top 5 by volume
    sorted_acts = sorted(activities, key=lambda x: x.get("volume", 0), reverse=True)
    for a in sorted_acts[:5]:
        logger.info(f"{a['ticker']} | {a['option_type']} | volume: {a['volume']} | ratio: {a['volume_oi_ratio']}")

# try with lower thresholds
significant = filter_significant_options(activities, min_volume=100, min_ratio=1.5)
logger.info(f"Significant with lower thresholds (100 contracts, 1.5 ratio): {len(significant)}")

significant2 = filter_significant_options(activities, min_volume=50, min_ratio=1.0)
logger.info(f"Significant with very low thresholds (50 contracts, 1.0 ratio): {len(significant2)}")