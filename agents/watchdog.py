from datetime import datetime, timezone, timedelta
from database.db import get_session, init_db, Trader, Signal, WatchdogState
from core.sec import get_form4_rss_feed, parse_filing_date, get_cik_from_ticker
from core.options import get_unusual_options_activity, filter_significant_options, WATCHLIST
from core.portfolio import get_top_traders_from_openinsider, get_finviz_insider_trades
from core.stocks import get_stock_price
from utils.config import load_config
from utils.logger import logger
import json
import re
import requests
import feedparser


def get_leaderboard() -> list:
    session = get_session()
    try:
        traders = session.query(Trader).all()
        result = []
        for t in traders:
            result.append({
                "id": t.id,
                "name": t.name,
                "ticker": t.ticker,
                "source": t.source,
                "sharpe": t.sharpe
            })
        logger.info(f"Watchdog loaded {len(result)} traders from leaderboard")
        return result
    except Exception as e:
        logger.error(f"Error loading leaderboard: {e}")
        return []
    finally:
        session.close()


def get_last_checked(ticker: str) -> datetime:
    session = get_session()
    try:
        state = session.query(WatchdogState).filter_by(ticker=ticker).first()
        if state:
            return state.last_checked
        return datetime.now(timezone.utc) - timedelta(hours=24)
    except Exception as e:
        logger.error(f"Error getting last checked for {ticker}: {e}")
        return datetime.now(timezone.utc) - timedelta(hours=24)
    finally:
        session.close()


def update_last_checked(ticker: str) -> None:
    session = get_session()
    try:
        state = session.query(WatchdogState).filter_by(ticker=ticker).first()
        if state:
            state.last_checked = datetime.now(timezone.utc)
        else:
            session.add(WatchdogState(
                ticker=ticker,
                last_checked=datetime.now(timezone.utc)
            ))
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating last checked for {ticker}: {e}")
    finally:
        session.close()


def update_all_last_checked(traders: list) -> None:
    tickers = set(t["ticker"].upper() for t in traders if t.get("ticker"))
    for ticker in tickers:
        update_last_checked(ticker)


def write_signal(trader_id: str, ticker: str, signal_type: str,
                 direction: str, size: float, price: float,
                 source: str, raw_data: dict) -> None:
    session = get_session()
    try:
        signal = Signal(
            trader_id=trader_id,
            ticker=ticker,
            signal_type=signal_type,
            direction=direction,
            size=size,
            price_at_signal=price,
            source=source,
            raw_data=json.dumps(raw_data),
            timestamp=datetime.now(timezone.utc),
            processed=0
        )
        session.add(signal)
        session.commit()
        logger.info(f"Signal written — {ticker} | {signal_type} | {direction} | ${size} | source: {source}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error writing signal: {e}")
    finally:
        session.close()


def signal_already_exists(ticker: str, signal_type: str, hours: int = 24) -> bool:
    session = get_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        count = session.query(Signal).filter(
            Signal.ticker == ticker,
            Signal.signal_type == signal_type,
            Signal.timestamp >= cutoff
        ).count()
        return count > 0
    except Exception as e:
        logger.error(f"Error checking signal existence: {e}")
        return False
    finally:
        session.close()


def build_tracked_tickers(traders: list) -> dict:
    tracked = {}
    for t in traders:
        ticker = t.get("ticker", "").upper()
        if not ticker:
            continue
        if ticker not in tracked:
            tracked[ticker] = []
        tracked[ticker].append(t)
    return tracked


def check_insider_filings(traders: list) -> int:
    logger.info("Watchdog — checking SEC EDGAR for tracked insider filings")

    tracked_tickers = build_tracked_tickers(traders)
    if not tracked_tickers:
        return 0

    signals_fired = 0

    for ticker, trader_list in tracked_tickers.items():
        try:
            cik = get_cik_from_ticker(ticker)
            if not cik:
                continue

            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=5&search_text=&output=atom"
            response = requests.get(
                url,
                headers={"User-Agent": "StockBot your-email@gmail.com"},
                timeout=10
            )
            feed = feedparser.parse(response.text)

            last_checked = get_last_checked(ticker)

            for entry in feed.entries:
                filing_date_str = entry.get("filing-date", "") or entry.get("updated", "")
                if not filing_date_str:
                    continue

                filing_date = parse_filing_date(filing_date_str[:10])
                if not filing_date:
                    continue

                if filing_date.tzinfo is None:
                    filing_date = filing_date.replace(tzinfo=timezone.utc)
                if last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=timezone.utc)

                if filing_date <= last_checked:
                    continue

                if signal_already_exists(ticker, "insider_filing", hours=24):
                    continue

                current_price = get_stock_price(ticker) or 0.0
                primary_trader = trader_list[0]

                write_signal(
                    trader_id=primary_trader["id"],
                    ticker=ticker,
                    signal_type="insider_filing",
                    direction="BULLISH",
                    size=0.0,
                    price=current_price,
                    source="sec_edgar",
                    raw_data={
                        "title": entry.get("title", ""),
                        "link": entry.get("filing-href", ""),
                        "filing_date": filing_date_str,
                        "insider_count": len(trader_list),
                        "traders": [t["id"] for t in trader_list]
                    }
                )
                signals_fired += 1
                break

        except Exception as e:
            logger.warning(f"Error checking filings for {ticker}: {e}")
            continue

    logger.info(f"Watchdog — {signals_fired} insider filing signals fired")
    return signals_fired


def check_portfolio_activity(traders: list, config: dict) -> int:
    logger.info("Watchdog — checking OpenInsider and Finviz for new trades")

    tracked_tickers = build_tracked_tickers(traders)
    min_value = config["watchdog"]["min_insider_buy_value"]

    all_trades = []
    all_trades.extend(get_top_traders_from_openinsider())
    all_trades.extend(get_finviz_insider_trades())

    signals_fired = 0
    seen_tickers = set()

    for trade in all_trades:
        try:
            ticker = trade.get("ticker", "").strip().upper()
            trade_type = trade.get("trade_type", "").lower()
            trade_date_str = trade.get("trade_date", "")

            if not ticker or ticker not in tracked_tickers:
                continue
            if ticker in seen_tickers:
                continue
            if "sale" in trade_type or "sell" in trade_type or "option" in trade_type:
                continue

            value_str = str(trade.get("value", "0")).replace(",", "").replace("$", "")
            try:
                value = float(value_str)
            except (ValueError, TypeError):
                value = 0.0

            if value < min_value:
                continue

            trade_date = parse_filing_date(str(trade_date_str)[:10])
            if not trade_date:
                continue

            last_checked = get_last_checked(ticker)

            if trade_date.tzinfo is None:
                trade_date = trade_date.replace(tzinfo=timezone.utc)
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)

            if trade_date <= last_checked:
                continue

            if signal_already_exists(ticker, "insider_purchase", hours=24):
                continue

            trader_list = tracked_tickers[ticker]
            primary_trader = trader_list[0]
            current_price = get_stock_price(ticker) or 0.0

            write_signal(
                trader_id=primary_trader["id"],
                ticker=ticker,
                signal_type="insider_purchase",
                direction="BULLISH",
                size=value,
                price=current_price,
                source=trade.get("source", "portfolio"),
                raw_data={
                    **trade,
                    "insider_count": len(trader_list),
                    "traders": [t["id"] for t in trader_list]
                }
            )
            signals_fired += 1
            seen_tickers.add(ticker)

        except Exception as e:
            logger.warning(f"Error processing portfolio trade: {e}")
            continue

    logger.info(f"Watchdog — {signals_fired} portfolio signals fired")
    return signals_fired


def check_options_activity(traders: list, config: dict) -> int:
    logger.info("Watchdog — checking unusual options activity")

    # use broad watchlist not just leaderboard tickers
    ticker_list = WATCHLIST
    tracked_tickers = build_tracked_tickers(traders)

    activities = get_unusual_options_activity(tickers=ticker_list)
    if not activities:
        return 0

    min_contracts = config["watchdog"]["min_option_contracts"]
    min_ratio = config["watchdog"]["unusual_options_volume_threshold"]
    significant = filter_significant_options(
        activities,
        min_volume=min_contracts,
        min_ratio=min_ratio
    )

    signals_fired = 0
    for signal in significant:
        try:
            ticker = signal.get("ticker", "").upper()

            if signal_already_exists(ticker, "unusual_options", hours=24):
                continue

            # use leaderboard trader if exists, otherwise generic
            if ticker in tracked_tickers:
                trader_list = tracked_tickers[ticker]
                primary_trader = trader_list[0]
                trader_id = primary_trader["id"]
            else:
                trader_id = f"options_{ticker}"

            direction = signal.get("direction", "BULLISH")
            volume = signal.get("volume", 0)
            current_price = get_stock_price(ticker) or 0.0

            write_signal(
                trader_id=trader_id,
                ticker=ticker,
                signal_type="unusual_options",
                direction=direction,
                size=float(volume),
                price=current_price,
                source="yfinance_options",
                raw_data=signal
            )
            signals_fired += 1

        except Exception as e:
            logger.warning(f"Error processing options signal: {e}")
            continue

    logger.info(f"Watchdog — {signals_fired} options signals fired")
    return signals_fired


def run_watchdog():
    logger.info("Watchdog starting")
    config = load_config()
    init_db()

    traders = get_leaderboard()
    if not traders:
        logger.warning("Watchdog — leaderboard is empty, run Scout first")
        return

    total_signals = 0
    total_signals += check_insider_filings(traders)
    total_signals += check_portfolio_activity(traders, config)
    total_signals += check_options_activity(traders, config)

    update_all_last_checked(traders)

    logger.info(f"Watchdog complete — {total_signals} total signals fired")
    return total_signals

if __name__ == "__main__":
    run_watchdog()