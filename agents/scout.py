from datetime import datetime, timezone, timedelta
from database.db import get_session, init_db, CandidateTrader, Trader
from core.sec import get_recent_form4_fillings, get_form4_rss_feed, extract_ticker_from_filing, parse_filing_date, get_insider_filings_by_name, get_ticker_from_cik, get_cik_from_ticker
from core.portfolio import get_all_portfolio_signals, parse_trade_amount
from core.options import get_unusual_options_activity, filter_significant_options
from core.scoring import score_insider, score_politician, passes_thresholds, calculate_sharpe, calculate_win_rate, calculate_roi, calculate_avg_return
from core.stocks import get_return_after_date, get_stock_price
from utils.config import load_config
from utils.logger import logger

def process_insider_filings(config: dict) -> int:
    logger.info("Scout — processing insider filings from SEC EDGAR")
    filings = get_recent_form4_fillings(days_back=7)
    if not filings:
        logger.warning("No insider filings found")
        return 0

    added = 0
    processed_tickers = set()

    for filing in filings:
        try:
            source = filing.get("_source", {})
            display_names = source.get("display_names", [])
            file_date = source.get("file_date", "")
            ciks = source.get("ciks", [])

            if not display_names or not ciks:
                continue

            # company is always the second entry in display_names
            company_name = display_names[-1].split("(")[0].strip() if display_names else ""
            company_cik = ciks[-1] if len(ciks) > 1 else ciks[0]
            insider_name = display_names[0].split("(")[0].strip() if display_names else ""

            if not company_name or not company_cik:
                continue

            # get ticker from company CIK
            ticker = get_ticker_from_cik(company_cik)
            if not ticker:
                logger.info(f"Could not find ticker for {company_name} — skipping")
                continue

            if ticker in processed_tickers:
                continue
            processed_tickers.add(ticker)

            trade_date = parse_filing_date(file_date)
            if not trade_date:
                continue

            # fetch full historical filings for this ticker
            historical_filings = get_insider_filings_by_name(company_name, ticker, cik = company_cik)
            if not historical_filings:
                continue

            scores = score_insider(historical_filings, ticker, days=30)
            if not scores:
                continue

            if passes_thresholds(scores, config):
                trader_id = f"insider_{ticker}_{insider_name[:20]}"
                upsert_candidate(
                    trader_id=trader_id,
                    name=f"{insider_name} — {company_name}",
                    source="insider",
                    ticker=ticker,
                    scores=scores
                )
                added += 1

        except Exception as e:
            logger.warning(f"Error processing filing: {e}")
            continue

    logger.info(f"Scout — added {added} insider candidates")
    return added
def process_portfolio_signals(config: dict) -> int:
    logger.info("Scout — processing portfolio signals")
    signals = get_all_portfolio_signals()
    if not signals:
        logger.warning("No portfolio signals found")
        return 0

    added = 0
    processed_tickers = set()

    for signal in signals:
        try:
            ticker = signal.get("ticker", "").strip()
            trader_name = (
                signal.get("insider_name") or
                signal.get("politician") or
                "Unknown"
            )
            trade_type = signal.get("trade_type", "").lower()

            if not ticker:
                continue
            if "sale" in trade_type or "sell" in trade_type:
                continue
            if ticker in processed_tickers:
                continue
            processed_tickers.add(ticker)

            # look up company CIK from ticker
            cik = get_cik_from_ticker(ticker)
            if not cik:
                logger.info(f"Could not find CIK for {ticker} — skipping")
                continue

            # fetch full historical filings using CIK
            historical_filings = get_insider_filings_by_name(
                ticker, ticker, cik=cik
            )
            if not historical_filings:
                continue

            scores = score_insider(historical_filings, ticker, days=30)
            if not scores:
                continue

            if passes_thresholds(scores, config):
                trader_id = f"portfolio_{ticker}_{trader_name[:20]}"
                upsert_candidate(
                    trader_id=trader_id,
                    name=f"{trader_name} — {ticker}",
                    source="portfolio",
                    ticker=ticker,
                    scores=scores
                )
                added += 1

        except Exception as e:
            logger.warning(f"Error processing portfolio signal: {e}")
            continue

    logger.info(f"Scout — added {added} portfolio candidates")
    return added

def process_options_signals(config: dict) -> int:
    logger.info("Scout — processing unusual options signals")
    activities = get_unusual_options_activity()
    if not activities:
        logger.warning("No options activity found")
        return 0

    significant = filter_significant_options(
        activities,
        min_volume=config["watchdog"]["min_option_contracts"],
        min_ratio=config["analyst"]["min_conviction_score"] * 100
    )

    added = 0
    for signal in significant:
        try:
            ticker = signal.get("ticker", "")
            if not ticker:
                continue

            direction = signal.get("direction")
            if not direction:
                logger.warning(f"No direction for {ticker} options signal — skipping")
                continue

            current_price = get_stock_price(ticker)
            if not current_price:
                continue

            trader_id = f"options_{ticker}_{signal.get('option_type', '')}_{signal.get('expiry', '')}"

            scores = {
                "sharpe": 0.5,
                "win_rate": 0.5,
                "roi": 0.0,
                "avg_return": 0.0,
                "total_signals": 1
            }

            upsert_candidate(
                trader_id=trader_id,
                name=f"Options flow — {ticker}",
                source="options",
                ticker=ticker,
                scores=scores,
                direction=direction,
                price_at_signal=current_price
            )
            added += 1

        except Exception as e:
            logger.warning(f"Error processing options signal: {e}")
            continue

    logger.info(f"Scout — added {added} options candidates")
    return added

def upsert_candidate(trader_id: str, name: str, source: str, ticker: str, scores: dict, direction: str = None, price_at_signal: float = None) -> None:
    session = get_session()
    try:
        existing = session.query(CandidateTrader).filter_by(id=trader_id).first()
        if existing:
            existing.sharpe = scores.get("sharpe", 0.0)
            existing.win_rate = scores.get("win_rate", 0.0)
            existing.roi = scores.get("roi", 0.0)
            existing.avg_return = scores.get("avg_return", 0.0)
            existing.total_signals = scores.get("total_signals", 0)
            existing.last_scored = datetime.now(timezone.utc)
            existing.last_seen = datetime.now(timezone.utc)
            existing.times_seen = (existing.times_seen or 0) + 1
            existing.status = "candidate"
        else:
            session.add(CandidateTrader(
                id=trader_id,
                name=name,
                source=source,
                ticker=ticker,
                sharpe=scores.get("sharpe", 0.0),
                win_rate=scores.get("win_rate", 0.0),
                roi=scores.get("roi", 0.0),
                avg_return=scores.get("avg_return", 0.0),
                total_signals=scores.get("total_signals", 0),
                last_scored=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                times_seen=1,
                status="candidate"
            ))
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error upserting candidate {trader_id}: {e}")
    finally:
        session.close()

def update_leaderboard(config: dict) -> None:
    top_n = config["scout"]["top_n_traders"]
    min_sharpe = config["scout"]["min_sharpe"]
    min_trades = config["scout"]["min_trades"]

    session = get_session()
    try:
        # hall of fame — proven traders never removed
        hall_of_fame = session.query(CandidateTrader).filter(
            CandidateTrader.times_seen >= 10,
            CandidateTrader.sharpe >= 1.0,
            CandidateTrader.status != "eliminated"
        ).all()

        hall_of_fame_ids = {c.id for c in hall_of_fame}
        logger.info(f"Hall of fame traders: {len(hall_of_fame_ids)}")

        # regular candidates passing thresholds
        candidates = session.query(CandidateTrader).filter(
            CandidateTrader.status == "candidate",
            CandidateTrader.sharpe >= min_sharpe,
            CandidateTrader.total_signals >= min_trades
        ).order_by(CandidateTrader.sharpe.desc()).limit(top_n).all()

        # combine hall of fame with regular candidates
        all_candidate_ids = {c.id for c in candidates}
        combined = list(candidates)

        for hof in hall_of_fame:
            if hof.id not in all_candidate_ids:
                combined.append(hof)
                logger.info(f"Hall of fame preserved: {hof.ticker} — sharpe: {hof.sharpe} | times_seen: {hof.times_seen}")

        # sort combined by sharpe
        combined.sort(key=lambda x: x.sharpe, reverse=True)
        combined = combined[:top_n]

        if not combined:
            logger.warning("No candidates found — leaderboard not updated")
            return

        session.query(Trader).delete()

        for c in combined:
            session.add(Trader(
                id=c.id,
                name=c.name,
                source=c.source,
                ticker=c.ticker,
                sharpe=c.sharpe,
                win_rate=c.win_rate,
                roi=c.roi,
                total_signals=c.total_signals,
                avg_return=c.avg_return,
                last_updated=datetime.now(timezone.utc)
            ))
            c.status = "top20"

        session.commit()
        logger.info(f"Leaderboard updated with {len(combined)} traders")

    except Exception as e:
        session.rollback()
        logger.error(f"Error updating leaderboard: {e}")
    finally:
        session.close()

def run_scout():
    logger.info("Scout starting")
    config = load_config()
    init_db()
    total = 0
    total += process_insider_filings(config)
    total+= process_options_signals(config)
    total+= process_portfolio_signals(config)

    logger.info(f"Scout discovered {total} total candidates")

    update_leaderboard(config)
    logger.info("Scout run complete")
if __name__ == "__main__":
    run_scout()
