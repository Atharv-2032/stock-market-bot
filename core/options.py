import yfinance as yf
import pandas as pd
from datetime import datetime
from utils.logger import logger

# Top 50 most liquid US stocks — best for options activity detection
WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "CVX",
    "MRK", "ABBV", "LLY", "PEP", "KO", "BAC", "PFE", "TMO", "COST",
    "DIS", "CSCO", "ABT", "MCD", "ACN", "CRM", "NEE", "NKE", "BMY",
    "RTX", "QCOM", "HON", "IBM", "GS", "CAT", "AMGN", "SPGI", "BLK",
    "INTU", "NOW", "AMAT", "AMD", "INTC"
]

def get_options_chain(ticker:str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return {}
        
        nearest_expiry = expirations[0]
        chain = stock.option_chain(nearest_expiry)
        return{
            "ticker": ticker,
            "expiry": nearest_expiry,
            "calls": chain.calls,
            "puts": chain.puts
        }
    except Exception as e:
        logger.warning(f"Error fetching options chain for {ticker}: {e}")
        return {}

def calculate_unusual_activity(chain:dict)->list:
    if not chain:
        return []

    unusual = []
    ticker = chain["ticker"]
    expiry = chain["expiry"]

    for option_type, df in [("CALL", chain["calls"]), ("PUT", chain["puts"])]:
        if df is None or df.empty:
            continue
        try:
            for _, row in df.iterrows():
                volume = row.get("volume", 0)
                open_interest = row.get("openInterest", 0)
                strike = row.get("strike", 0)
                last_price = row.get("lastPrice", 0)

                if pd.isna(volume) or pd.isna(open_interest):
                    continue
                if open_interest == 0:
                    continue

                volume = int(volume)
                open_interest = int(open_interest)
                ratio = volume / open_interest

                unusual.append({
                    "ticker": ticker,
                    "option_type": option_type,
                    "strike": strike,
                    "expiry": expiry,
                    "volume": volume,
                    "open_interest": open_interest,
                    "volume_oi_ratio": round(ratio, 2),
                    "last_price": last_price,
                    "direction": "BULLISH" if option_type == "CALL" else "BEARISH",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            logger.warning(f"Error processing {option_type} chain for {ticker}: {e}")
            continue

    return unusual

def get_unusual_options_activity(tickers:list = None) -> list:
    if tickers is None:
        tickers = WATCHLIST

    all_unusual = []
    for ticker in tickers:
        try:
            chain = get_options_chain(ticker)
            if not chain:
                continue
            unusual = calculate_unusual_activity(chain)
            all_unusual.extend(unusual)
        except Exception as e:
            logger.warning(f"Error processing {ticker}: {e}")
            continue

    logger.info(f"Fetched {len(all_unusual)} options records across {len(tickers)} tickers")
    return all_unusual

def filter_significant_options(activities: list, min_volume: int = 500, min_ratio: float = 2.0) -> list:
    significant = []
    for activity in activities:
        if not activity:
            continue
        volume = activity.get("volume", 0)
        ratio = activity.get("volume_oi_ratio", 0)
        if volume >= min_volume and ratio >= min_ratio:
            significant.append(activity)
    logger.info(f"Filtered to {len(significant)} significant options signals")
    return significant

def parse_options_signal(activity: dict) -> dict:
    return activity