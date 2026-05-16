import requests
from bs4 import BeautifulSoup
from utils.logger import logger
from core.sec import parse_filing_date

logger.info("Testing Finviz insider trading")
try:
    url = "https://finviz.com/insidertrading.ashx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://finviz.com",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"class": "styled-table-new"})

    if table:
        rows = table.find_all("tr")[1:]
        logger.info(f"Total rows: {len(rows)}")

        for row in rows[:5]:
            cols = [td.text.strip() for td in row.find_all("td")]
            if len(cols) < 9:
                continue

            raw_date = cols[3].strip()
            parsed_date = parse_filing_date(raw_date)

            logger.info(f"Ticker: {cols[0]}")
            logger.info(f"Owner: {cols[1]}")
            logger.info(f"Title: {cols[2]}")
            logger.info(f"Raw date: {raw_date}")
            logger.info(f"Parsed date: {parsed_date}")
            logger.info(f"Transaction: {cols[4]}")
            logger.info(f"Price: {cols[5]}")
            logger.info(f"Quantity: {cols[6]}")
            logger.info(f"Value: {cols[7]}")
            logger.info("---")
    else:
        logger.warning("Table not found")

except Exception as e:
    logger.error(f"Error: {e}")
    logger.error(f"Error: {e}")
import requests
from bs4 import BeautifulSoup
from utils.logger import logger

# test the date parsing directly
test_date = "May 11 '26"
logger.info(f"Original: '{test_date}'")
logger.info(f"Repr: {repr(test_date)}")

cleaned = test_date.replace("'", "")
logger.info(f"After replace: '{cleaned}'")
logger.info(f"Repr after: {repr(cleaned)}")

from datetime import datetime
formats = ["%b %d %y", "%B %d %y"]
for fmt in formats:
    try:
        result = datetime.strptime(cleaned, fmt)
        logger.info(f"Parsed with {fmt}: {result}")
    except ValueError as e:
        logger.info(f"Failed {fmt}: {e}")

from core.sec import parse_filing_date
from utils.logger import logger

test_dates = ["May 11 '26", "May 08 '26", "2026-05-01", "Mon, 11 May 2026 10:23:00 +0000"]
for d in test_dates:
    result = parse_filing_date(d)
    logger.info(f"'{d}' → {result}")