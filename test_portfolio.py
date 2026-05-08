from utils.logger import logger
from core.sec import get_cik_from_ticker, get_insider_filings_by_name
from core.scoring import score_insider
from utils.config import load_config

config = load_config()

# test with a few tickers from OpenInsider
test_tickers = ["POOL", "NVDA", "AAPL", "AFL"]

for ticker in test_tickers:
    logger.info(f"Testing {ticker}")
    cik = get_cik_from_ticker(ticker)
    logger.info(f"  CIK: {cik}")
    if cik:
        filings = get_insider_filings_by_name(ticker, ticker, cik=cik)
        logger.info(f"  Filings: {len(filings)}")
        if filings:
            scores = score_insider(filings, ticker, days=30)
            logger.info(f"  Scores: {scores}")