from datetime import datetime, timezone, timedelta
from database.db import get_session, init_db, Signal, Verdict, Trader
from core.stocks import get_stock_price, get_price_on_date, get_average_daily_volume
from core.risk import calculate_price_drift, calculate_conviction_score, calculate_max_safe_size
from core.llm import classify_trade_signal
from core.sec import parse_filing_date
from utils.config import load_config
from utils.logger import logger
import json


def get_unprocessed_signals() -> list:
    session = get_session()
    try:
        signals = session.query(Signal).filter(
            Signal.processed == 0
        ).order_by(Signal.timestamp.asc()).all()
        result = []
        for s in signals:
            result.append({
                "id": s.id,
                "trader_id": s.trader_id,
                "ticker": s.ticker,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "size": s.size,
                "price_at_signal": s.price_at_signal,
                "source": s.source,
                "raw_data": json.loads(s.raw_data) if s.raw_data else {},
                "timestamp": s.timestamp
            })
        logger.info(f"Analyst found {len(result)} unprocessed signals")
        return result
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        return []
    finally:
        session.close()


def mark_signal_processed(signal_id: int) -> None:
    session = get_session()
    try:
        signal = session.query(Signal).filter_by(id=signal_id).first()
        if signal:
            signal.processed = 1
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error marking signal processed: {e}")
    finally:
        session.close()


def write_verdict(signal_id: int, verdict: str, staleness: float,
                  conviction: float, signal_count: int, safe_size: float,
                  llm_score: float, llm_reasoning: str) -> None:
    session = get_session()
    try:
        session.add(Verdict(
            signal_id=signal_id,
            verdict=verdict,
            staleness_score=staleness,
            conviction_score=conviction,
            signal_count=signal_count,
            safe_size=safe_size,
            llm_score=llm_score,
            llm_reasoning=llm_reasoning,
            timestamp=datetime.now(timezone.utc)
        ))
        session.commit()
        logger.info(f"Verdict written — signal {signal_id}: {verdict} | conviction: {conviction:.3f} | llm: {llm_score:.3f}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error writing verdict: {e}")
    finally:
        session.close()


def get_reference_price(signal: dict) -> float | None:
    ticker = signal["ticker"]
    signal_type = signal["signal_type"]
    raw_data = signal["raw_data"]

    if signal_type == "unusual_options":
        return signal.get("price_at_signal")

    date_str = (
        raw_data.get("trade_date") or
        raw_data.get("filing_date") or
        raw_data.get("date") or
        ""
    )

    if date_str:
        try:
            trade_date = parse_filing_date(str(date_str)[:10])
            if trade_date:
                price = get_price_on_date(ticker, trade_date)
                if price:
                    return price
        except Exception:
            pass

    return signal.get("price_at_signal")


def get_signal_count(ticker: str, hours: int = 24) -> int:
    session = get_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        count = session.query(Signal).filter(
            Signal.ticker == ticker,
            Signal.timestamp >= cutoff
        ).count()
        return count
    except Exception as e:
        logger.error(f"Error counting signals: {e}")
        return 1
    finally:
        session.close()


def get_trader_info(trader_id: str) -> dict:
    session = get_session()
    try:
        trader = session.query(Trader).filter_by(id=trader_id).first()
        if trader:
            return {
                "name": trader.name,
                "source": trader.source,
                "sharpe": trader.sharpe,
                "win_rate": trader.win_rate
            }
        return {}
    except Exception as e:
        logger.error(f"Error fetching trader: {e}")
        return {}
    finally:
        session.close()


def analyse_signal(signal: dict, config: dict) -> str:
    ticker = signal["ticker"]
    signal_id = signal["id"]
    raw_data = signal.get("raw_data", {})

    max_drift = config["analyst"]["max_price_drift"]
    min_conviction = config["analyst"]["min_conviction_score"]
    max_impact = config["analyst"]["max_market_impact"]
    min_signals = config["analyst"]["min_signals_required"]
    min_options_ratio = config["analyst"].get("min_options_ratio", 1.5)

    # always initialise so they're never undefined
    safe_size = 0.0
    conviction = min_conviction

    logger.info(f"Analysing signal {signal_id} — {ticker} | {signal['signal_type']} | {signal['direction']}")

    # ── Filter 1 — Price staleness ────────────────────────────────
    current_price = get_stock_price(ticker)
    if not current_price:
        logger.info(f"Signal {signal_id} SKIP — could not fetch current price for {ticker}")
        write_verdict(signal_id, "SKIP", 1.0, 0.0, 1, 0.0, 0.0, "Could not fetch current price")
        return "SKIP"

    reference_price = get_reference_price(signal)
    if not reference_price:
        reference_price = current_price

    staleness = calculate_price_drift(reference_price, current_price)
    if staleness > max_drift:
        logger.info(f"Signal {signal_id} SKIP — price drifted {staleness:.1%} (max {max_drift:.1%})")
        write_verdict(signal_id, "SKIP", staleness, 0.0, 1, 0.0, 0.0,
                     f"Price drifted {staleness:.1%} since signal")
        return "SKIP"

    logger.info(f"Filter 1 passed — staleness: {staleness:.1%}")

    # ── Filter 2 — Conviction score ───────────────────────────────
    if signal["signal_type"] == "unusual_options":
        ratio = float(raw_data.get("volume_oi_ratio", 0))
        conviction = min(ratio / 10.0, 1.0)
        if ratio < min_options_ratio:
            logger.info(f"Signal {signal_id} SKIP — options ratio {ratio:.2f} below min {min_options_ratio}")
            write_verdict(signal_id, "SKIP", staleness, conviction, 1, 0.0, 0.0,
                         f"Options ratio {ratio:.2f} below threshold {min_options_ratio}")
            return "SKIP"
        logger.info(f"Filter 2 passed — options ratio: {ratio:.2f} | conviction: {conviction:.3f}")

    else:
        # insider_filing and insider_purchase
        avg_volume = get_average_daily_volume(ticker)
        trade_size = signal.get("size", 0) or 0
        if trade_size > 0 and avg_volume > 0:
            conviction = calculate_conviction_score(trade_size, avg_volume, current_price)
        else:
            conviction = min_conviction
        if conviction < min_conviction:
            logger.info(f"Signal {signal_id} SKIP — conviction {conviction:.4f} below min {min_conviction}")
            write_verdict(signal_id, "SKIP", staleness, conviction, 1, 0.0, 0.0,
                         f"Conviction {conviction:.4f} below threshold")
            return "SKIP"
        logger.info(f"Filter 2 passed — conviction: {conviction:.4f}")

    # ── Filter 3 — Market impact ──────────────────────────────────
    safe_size = calculate_max_safe_size(ticker, max_impact)
    budget = config["executor"]["budget_per_trade"]

    if safe_size < budget:
        logger.info(f"Signal {signal_id} SKIP — safe size ${safe_size:.0f} below budget ${budget}")
        write_verdict(signal_id, "SKIP", staleness, conviction, 1, safe_size, 0.0,
                     f"Market too illiquid — safe size ${safe_size:.0f}")
        return "SKIP"

    logger.info(f"Filter 3 passed — safe size: ${safe_size:,.0f}")

    # ── Filter 4 — Signal count ───────────────────────────────────
    signal_count = get_signal_count(ticker, hours=24)
    if signal_count < min_signals:
        logger.info(f"Signal {signal_id} WATCH — only {signal_count} signal(s) in 24h")
        write_verdict(signal_id, "WATCH", staleness, conviction, signal_count, safe_size, 0.0,
                     f"Only {signal_count} signal(s) — watching for confirmation")
        return "WATCH"

    logger.info(f"Filter 4 passed — signal count: {signal_count}")

    # ── GPT-4o classification ─────────────────────────────────────
    trader_info = get_trader_info(signal["trader_id"])

    llm_result = classify_trade_signal(
        ticker=ticker,
        signal_type=signal["signal_type"],
        direction=signal["direction"],
        insider_title=raw_data.get("title", ""),
        company=raw_data.get("company", ticker),
        extra_context=(
            f"Sharpe: {trader_info.get('sharpe', 'N/A')} | "
            f"Win rate: {trader_info.get('win_rate', 'N/A')} | "
            f"Signals in 24h: {signal_count} | "
            f"Options ratio: {raw_data.get('volume_oi_ratio', 'N/A')}"
        )
    )

    llm_score = llm_result.get("composite", 0.5)
    catalyst = llm_result.get("catalyst", "Unknown")
    risk_level = llm_result.get("risk_level", "MEDIUM")

    if llm_score >= 0.6 and risk_level != "HIGH":
        verdict = "TRADE"
    elif llm_score >= 0.4:
        verdict = "WATCH"
    else:
        verdict = "SKIP"

    write_verdict(
        signal_id=signal_id,
        verdict=verdict,
        staleness=staleness,
        conviction=conviction,
        signal_count=signal_count,
        safe_size=safe_size,
        llm_score=llm_score,
        llm_reasoning=f"{catalyst} | risk: {risk_level}"
    )

    logger.info(f"Signal {signal_id} → {verdict} | llm: {llm_score:.3f} | catalyst: {catalyst}")
    return verdict


def run_analyst() -> dict:
    logger.info("Analyst starting")
    config = load_config()
    init_db()

    signals = get_unprocessed_signals()
    if not signals:
        logger.info("Analyst — no unprocessed signals")
        return {"TRADE": 0, "WATCH": 0, "SKIP": 0}

    results = {"TRADE": 0, "WATCH": 0, "SKIP": 0}

    for signal in signals:
        try:
            verdict = analyse_signal(signal, config)
            results[verdict] = results.get(verdict, 0) + 1
            mark_signal_processed(signal["id"])
        except Exception as e:
            logger.error(f"Error analysing signal {signal['id']}: {e}")
            mark_signal_processed(signal["id"])

    logger.info(f"Analyst complete — TRADE: {results['TRADE']} | WATCH: {results['WATCH']} | SKIP: {results['SKIP']}")
    return results


if __name__ == "__main__":
    run_analyst()