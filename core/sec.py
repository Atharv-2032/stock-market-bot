import requests
import feedparser
from datetime import datetime, timedelta
from utils.logger import logger

SEC_BASE = "https://efts.sec.gov"
SEC_EDGAR = "https://www.sec.gov"
HEADERS = {"User-Agent": "stockbot atharv.gupta2026@gmail.com"}

def get_recent_form4_fillings(days_back: int = 7) -> list:
    try:
        url = f"{SEC_BASE}/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt={(datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')}&enddt={datetime.now().strftime('%Y-%m-%d')}&_source=period_of_report,entity_name,file_date,period_of_report&forms=4"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        filings = data.get("hits", {}).get("hits", [])
        logger.info(f"Fetched {len(filings)} Form 4 filings from last {days_back} days")
        return filings
    except Exception as e:
        logger.error(f"Error fetching Form 4 filings: {e}")
        return []
def get_insider_trades(cik: str) -> list:
    try:
        url = f"{SEC_EDGAR}/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40&search_text=&output=atom"
        feed = feedparser.parse(url)
        trades = []
        for entry in feed.entries:
            trades.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "date": entry.get("published", ""),
                "summary": entry.get("summary", "")
            })
        logger.info(f"Fetched {len(trades)} filings for CIK {cik}")
        return trades
    except Exception as e:
        logger.error(f"Error fetching insider trades for CIK {cik}: {e}")
        return []

def search_company_cik(company_name: str) -> str | None:
    try:
        url = f"{SEC_EDGAR}/cgi-bin/browse-edgar?company={company_name}&CIK=&type=4&dateb=&owner=include&count=10&search_text=&action=getcompany&output=atom"
        feed = feedparser.parse(url)
        if feed.entries:
            first = feed.entries[0]
            title = first.get("title", "")
            parts = title.split("(")
            if len(parts) > 1:
                cik = parts[-1].replace(")", "").strip()
                return cik
        return None
    except Exception as e:
        logger.error(f"Error searching CIK for {company_name}: {e}")
        return None
def get_form4_rss_feed() -> list:
    try:
        url = f"{SEC_EDGAR}/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=40&search_text=&output=atom"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        filings = []
        for entry in feed.entries:
            title = entry.get("title", "")
            # only keep actual Form 4 filings
            if not title.startswith("4 -"):
                continue
            filings.append({
                "title": title,
                "link": entry.get("link", ""),
                "date": entry.get("published", ""),
                "summary": entry.get("summary", "")
            })
        logger.info(f"Fetched {len(filings)} recent Form 4 filings from RSS")
        return filings
    except Exception as e:
        logger.error(f"Error fetching Form 4 RSS feed: {e}")
        return []
   
def parse_filing_date(date_str: str) -> datetime | None:
    try:
        if not date_str:
            return None

        date_str = date_str.strip()

        # handle Finviz format: "May 11 '26" → "May 11 26"
        date_str_clean = date_str.replace("'", "")

        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S %z",
            "%b %d %y",
            "%B %d %y",
            "%m/%d/%Y",
            "%d-%b-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str_clean, fmt).replace(tzinfo=None)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None
    except Exception as e:
        logger.error(f"Error parsing date {date_str}: {e}")
        return None

def extract_ticker_from_filing(filing: dict) -> str | None:
    try:
        title = filing.get("title", "")
        summary = filing.get("summary", "")
        text = title + " " + summary
        import re
        matches = re.findall(r'\(([A-Z]{1,5})\)', text)
        if matches:
            return matches[0]
        return None
    except Exception as e:
        logger.error(f"Error extracting ticker: {e}")
        return None

def get_insider_filings_by_name(company_name: str, ticker: str, cik: str = None) -> list:
    try:
        if not cik:
            logger.warning(f"No CIK provided for {company_name} — skipping")
            return []

        url = f"{SEC_EDGAR}/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40&search_text=&output=atom"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        filings = []
        for entry in feed.entries:
            date = entry.get("filing-date", "") or entry.get("updated","")
            title = entry.get("title", "")
            if not date:
                continue
            clean_date = date[:10] if date else ""
            filings.append({
                "title": title,
                "link": entry.get("filing-href", ""),
                "filing_date": clean_date,
                "trade_date": clean_date,
                "ticker": ticker
            })

        logger.info(f"Fetched {len(filings)} historical filings for {ticker}")
        return filings

    except Exception as e:
        logger.error(f"Error fetching historical filings for {ticker}: {e}")
        return []

def get_ticker_from_cik(cik: str) -> str | None:
    try:
       
        url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        tickers = data.get("tickers", [])
        if tickers:
            return tickers[0].upper()
        return None
    except Exception as e:
        logger.warning(f"Error fetching ticker for CIK {cik}: {e}")
        return None

def get_cik_from_ticker(ticker: str) -> str | None:
    try:
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2024-01-01&enddt=2026-12-31&forms=4"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])
        for hit in hits:
            source = hit.get("_source", {})
            ciks = source.get("ciks", [])
            display_names = source.get("display_names", [])
            if len(ciks) >= 2 and len(display_names) >= 2:
                # return company CIK (last one)
                return ciks[-1]
        return None
    except Exception as e:
        logger.warning(f"Error finding CIK for ticker {ticker}: {e}")
        return None

    