from core.sec import get_insider_filings_by_name, get_ticker_from_cik
from utils.logger import logger

# Test with NOC - Northrop Grumman
from core.sec import get_insider_filings_by_name
from utils.logger import logger

filings = get_insider_filings_by_name("NORTHROP GRUMMAN CORP", "NOC", cik="0001133421")
logger.info(f"NOC historical filings: {len(filings)}")
if filings:
    logger.info(f"First filing: {filings[0]}")
    logger.info(f"Last filing: {filings[-1]}")

from core.sec import get_insider_filings_by_name
from core.scoring import score_insider
from utils.logger import logger

filings = get_insider_filings_by_name("NORTHROP GRUMMAN CORP", "NOC", cik="0001133421")
logger.info(f"NOC historical filings: {len(filings)}")

scores = score_insider(filings, "NOC", days=30)
logger.info(f"NOC scores: {scores}")