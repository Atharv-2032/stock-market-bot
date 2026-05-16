from core.sec import get_form4_trade_size
from utils.logger import logger

# use a real filing link from our earlier Scout runs
# NOC filing we saw earlier
test_link = "https://www.sec.gov/Archives/edgar/data/1133421/000162828026030668/0001628280-26-030668-index.htm"

logger.info("Testing Form 4 XML parsing")
size = get_form4_trade_size(test_link)
logger.info(f"Trade size: ${size:,.0f}")