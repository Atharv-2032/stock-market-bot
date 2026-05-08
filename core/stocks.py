import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from utils.logger import logger

def get_stock_price(ticker:str)->float|None:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period = "1d")
        if hist.empty:
            logger.warning(f"No price data for {ticker}")
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"Error fetching price for {ticker}: {e}")
        return None

def get_price_on_date(ticker:str,date:datetime)-> float|None:
    try:
        start = date.strftime("%Y-%m-%d")
        end = (date + timedelta(days=5)).strftime("%Y-%m-%d")
        stock = yf.Ticker(ticker)
        hist = stock.history(start = start, end = end)
        if hist.empty:
            logger.warning(f"No price data for {ticker} around {start}")
            return None
        return float(hist["Close"].iloc[0])
    except Exception as e:
        logger.error(f"Error fetching price for {ticker} on {date}: {e}")
        return None
    
def get_return_after_date(ticker:str, entry_date: datetime, days: int = 30)-> float|None:
    try:
        if entry_date > datetime.now():
            logger.warning(f"Entry date {entry_date} is in the future — skipping")
            return None
        entry_price  = get_price_on_date(ticker, entry_date)
        if not entry_price:
            return None
        exit_date = entry_date + timedelta(days = days)
        if exit_date > datetime.now():
            logger.warning(f"Exit date {exit_date} is in the future — skipping")
            return None
        exit_price = get_price_on_date(ticker, exit_date)
        if not exit_price:
            return None
        
        return (exit_price - entry_price)/entry_price
    except Exception as e:
        logger.error(f"Error calculating return for {ticker}: {e}")
        return None
    
def get_historical_prices(ticker:str, days: int = 90):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period = f"{days}d")
        if hist.empty:
            logger.warning(f"No historical data for {ticker}")
            return pd.DataFrame()
        return hist
    except Exception as e:
        logger.error(f"Error fetching historical data for {ticker}: {e}")
        return pd.DataFrame()

def get_average_daily_volume(ticker:str, days:int = 30) -> float:
    try:
        hist = get_historical_prices(ticker,days)
        if hist.empty:
            return 0.0
        return float(hist["Volume"].mean())
    except Exception as e:
        logger.error(f"Error calculating volume for {ticker}: {e}")
        return 0.0
    
def get_stock_info(ticker:str)->dict:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info()
        return{
            "ticker": ticker,
            "name": info.get("longName", ""),
            "sector": info.get("sector", ""),
            "market_cap": info.get("marketCap", 0),
            "avg_volume": info.get("averageVolume", 0),
            "current_price": info.get("currentPrice", 0)
        }
    except Exception as e:
        logger.error(f"Error fetching info for {ticker}: {e}")
        return {}



