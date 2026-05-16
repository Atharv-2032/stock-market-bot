import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from utils.logger import logger
from core.sec import parse_filing_date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}


def get_top_traders_from_openinsider() -> list:
    try:
        url = url = "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=90&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=100&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&Action=1"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        traders = []
        table = soup.find("table", {"class": "tinytable"})
        if not table:
            logger.warning("No table found on OpenInsider")
            return []
        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 10:
                traders.append({
                    "filing_date": cols[1].text.strip(),
                    "trade_date": cols[2].text.strip(),
                    "ticker": cols[3].text.strip(),
                    "company": cols[4].text.strip(),
                    "insider_name": cols[5].text.strip(),
                    "title": cols[6].text.strip(),
                    "trade_type": cols[7].text.strip(),
                    "price": cols[8].text.strip(),
                    "quantity": cols[9].text.strip(),
                    "source": "openinsider"
                })
        logger.info(f"Fetched {len(traders)} insider trades from OpenInsider")
        return traders
    except Exception as e:
        logger.error(f"Error fetching OpenInsider data: {e}")
        return []
def get_finviz_insider_trades() -> list:
    try:
        url = "https://finviz.com/insidertrading.ashx"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Referer": "https://finviz.com",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"class": "styled-table-new"})
        if not table:
            logger.warning("Finviz insider table not found")
            return []

        trades = []
        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = [td.text.strip() for td in row.find_all("td")]
            if len(cols) < 9:
                continue

            trade_type = cols[4].lower()
            if "sale" in trade_type or "option" in trade_type:
                continue

            raw_date = cols[3].strip()
            parsed_date = parse_filing_date(raw_date)

            trades.append({
                "ticker": cols[0].strip(),
                "insider_name": cols[1].strip(),
                "title": cols[2].strip(),
                "trade_date": parsed_date.strftime("%Y-%m-%d") if parsed_date else raw_date,
                "trade_type": cols[4].strip(),
                "price": cols[5].strip(),
                "quantity": cols[6].strip(),
                "value": cols[7].strip(),
                "source": "finviz"
            })

        logger.info(f"Fetched {len(trades)} insider trades from Finviz")
        return trades
    except Exception as e:
        logger.error(f"Error fetching Finviz insider trades: {e}")
        return []
def get_congress_trades() -> list:
    try:
        url = "https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt=2026-01-01&enddt=2026-12-31&forms=4"
        response = requests.get(
            "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        trades = []
        for trade in data[:100]:
            trades.append({
                "politician": trade.get("representative", ""),
                "ticker": trade.get("ticker", ""),
                "trade_type": trade.get("type", ""),
                "trade_date": trade.get("transaction_date", ""),
                "amount": trade.get("amount", ""),
                "source": "congress"
            })
        logger.info(f"Fetched {len(trades)} congressional trades")
        return trades
    except Exception as e:
        logger.error(f"Error fetching congressional trades: {e}")
        return []


def get_politician_trades() -> list:
    try:
        url = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        trades = []
        for trade in data[:100]:
            trades.append({
                "politician": trade.get("first_name", "") + " " + trade.get("last_name", ""),
                "ticker": trade.get("ticker", ""),
                "trade_type": trade.get("type", ""),
                "trade_date": trade.get("transaction_date", ""),
                "amount": trade.get("amount", ""),
                "source": "senate"
            })
        logger.info(f"Fetched {len(trades)} senate trades")
        return trades
    except Exception as e:
        logger.error(f"Error fetching senate trades: {e}")
        return []
    
def parse_trade_amount(amount_str: str) -> float:
    try:
        amount_str = str(amount_str).replace("$", "").replace(",", "").strip()
        ranges = {
            "1,001 - 15,000": 8000,
            "15,001 - 50,000": 32500,
            "50,001 - 100,000": 75000,
            "100,001 - 250,000": 175000,
            "250,001 - 500,000": 375000,
            "500,001 - 1,000,000": 750000,
            "1,000,001 - 5,000,000": 3000000,
            "5,000,001 - 25,000,000": 15000000,
            "25,000,001 - 50,000,000": 37500000
        }
        for range_str, midpoint in ranges.items():
            if range_str in amount_str:
                return float(midpoint)
        clean = re.sub(r'[^\d.]', '', amount_str)
        return float(clean) if clean else 0.0
    except Exception:
        return 0.0


def get_all_portfolio_signals() -> list:
    all_signals = []
    openinsider = get_top_traders_from_openinsider()
    all_signals.extend(openinsider)

    finviz = get_finviz_insider_trades()
    all_signals.extend(finviz)
    #congress = get_congress_trades()
    #all_signals.extend(congress)
    #senate = get_politician_trades()
    #all_signals.extend(senate)
    logger.info(f"Total portfolio signals: {len(all_signals)}")
    return all_signals