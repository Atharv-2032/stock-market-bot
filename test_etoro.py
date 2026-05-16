import requests
from utils.logger import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

# Test BullAware API
logger.info("Testing BullAware API")
try:
    # try fetching top eToro traders
    response = requests.get(
        "https://bullaware.com/api/etoro/top-traders",
        headers=HEADERS,
        timeout=10
    )
    logger.info(f"Status: {response.status_code}")
    logger.info(f"Response: {response.text[:500]}")
except Exception as e:
    logger.error(f"Error: {e}")

# Test eToro public API directly
logger.info("Testing eToro public stats endpoint")
try:
    response = requests.get(
        "https://www.etoro.com/api/logininfo/v1.1/users/davidcruz/stats",
        headers=HEADERS,
        timeout=10
    )
    logger.info(f"eToro stats status: {response.status_code}")
    logger.info(f"Response: {response.text[:500]}")
except Exception as e:
    logger.error(f"Error: {e}")

# Test eToro public portfolio endpoint
logger.info("Testing eToro public portfolio endpoint")
try:
    response = requests.get(
        "https://www.etoro.com/api/logininfo/v1.1/users/davidcruz/portfolio",
        headers=HEADERS,
        timeout=10
    )
    logger.info(f"eToro portfolio status: {response.status_code}")
    logger.info(f"Response: {response.text[:500]}")
except Exception as e:
    logger.error(f"Error: {e}")