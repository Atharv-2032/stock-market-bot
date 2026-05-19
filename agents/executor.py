from datetime import datetime, timezone, timedelta
from database.db import get_session, init_db, Verdict, Trade, Position, Signal
from core.stocks import get_stock_price, get_average_daily_volume
from core.risk import (
    calculate_position_size, calculate_stop_loss,
    calculate_take_profit, calculate_risk_ceiling,
    check_stop_loss, check_take_profit
)
from utils.config import load_config
from utils.logger import logger
import json
import time


def get_trade_verdicts() -> list:
    session = get_session()
    try:
        verdicts = session.query(Verdict).filter(
            Verdict.verdict == "TRADE"
        ).all()

        executed_signal_ids = {
            t.verdict_id for t in session.query(Trade).all()
        }

        result = []
        for v in verdicts:
            if v.id not in executed_signal_ids:
                signal = session.query(Signal).filter_by(id=v.signal_id).first()
                if signal:
                    type_bonus = 0.3 if signal.signal_type in ["insider_filing", "insider_purchase"] else 0.0
                    conviction = min(v.conviction_score or 0, 1.0)
                    count_bonus = min((v.signal_count or 1) - 1, 3)  # 0, 1, 2, or 3

                    priority = (
                        v.llm_score * 0.4 +
                        conviction  * 0.3 +
                        type_bonus  * 0.2 +
                        count_bonus * 0.1
                    )
                    result.append({
                        "verdict_id": v.id,
                        "signal_id": v.signal_id,
                        "ticker": signal.ticker,
                        "direction": signal.direction,
                        "safe_size": v.safe_size,
                        "conviction": v.conviction_score,
                        "llm_score": v.llm_score,
                        "llm_reasoning": v.llm_reasoning,
                        "signal_type": signal.signal_type,
                        "priority":priority,
                        "timestamp": v.timestamp
                    })

        result.sort(key=lambda x: x["priority"], reverse=True)

        logger.info(f"Executor found {len(result)} unexecuted TRADE verdicts")
        if result:
            logger.info(f"Top 5 by priority:")
            for r in result[:5]:
                logger.info(f"  {r['ticker']} | type:{r['signal_type']} | priority:{r['priority']:.3f} | llm:{r['llm_score']:.3f} | conviction:{r['conviction']:.3f}")

        return result
    except Exception as e:
        logger.error(f"Error fetching verdicts: {e}")
        return []
    finally:
        session.close()


def get_open_positions() -> list:
    session = get_session()
    try:
        return session.query(Position).all()
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return []
    finally:
        session.close()


def get_open_position_count() -> int:
    session = get_session()
    try:
        return session.query(Position).count()
    except Exception as e:
        logger.error(f"Error counting positions: {e}")
        return 0
    finally:
        session.close()


def get_daily_pnl() -> float:
    session = get_session()
    try:
        cutoff = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        trades_today = session.query(Trade).filter(
            Trade.timestamp >= cutoff,
            Trade.status == "closed"
        ).all()
        return sum(t.pnl for t in trades_today)
    except Exception as e:
        logger.error(f"Error calculating daily PnL: {e}")
        return 0.0
    finally:
        session.close()


def write_trade(verdict_id: int, ticker: str, direction: str,
                entry_price: float, size: float, stop_loss: float,
                take_profit: float, execution_mode: str) -> int | None:
    session = get_session()
    try:
        trade = Trade(
            verdict_id=verdict_id,
            ticker=ticker,
            direction=direction,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="open",
            exit_price=None,
            pnl=0.0,
            execution_mode=execution_mode,
            timestamp=datetime.now(timezone.utc)
        )
        session.add(trade)
        session.commit()
        logger.info(f"Trade recorded — {ticker} | {direction} | ${size:.2f} @ ${entry_price:.2f} | SL: ${stop_loss:.2f} | TP: ${take_profit:.2f}")
        return trade.id
    except Exception as e:
        session.rollback()
        logger.error(f"Error writing trade: {e}")
        return None
    finally:
        session.close()


def write_position(ticker: str, direction: str, size: float,
                   entry_price: float, stop_loss: float, take_profit: float) -> None:
    session = get_session()
    try:
        existing = session.query(Position).filter_by(ticker=ticker).first()
        if existing:
            logger.info(f"Position already exists for {ticker} — skipping")
            return

        session.add(Position(
            ticker=ticker,
            direction=direction,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now(timezone.utc)
        ))
        session.commit()
        logger.info(f"Position opened — {ticker} | {direction} | ${size:.2f} @ ${entry_price:.2f}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error writing position: {e}")
    finally:
        session.close()


def close_position(ticker: str, exit_price: float, trade_id: int) -> float:
    session = get_session()
    try:
        position = session.query(Position).filter_by(ticker=ticker).first()
        if not position:
            return 0.0

        if position.direction == "BULLISH":
            pnl = (exit_price - position.entry_price) / position.entry_price * position.size
        else:
            pnl = (position.entry_price - exit_price) / position.entry_price * position.size

        trade = session.query(Trade).filter_by(id=trade_id).first()
        if trade:
            trade.exit_price = exit_price
            trade.pnl = pnl
            trade.status = "closed"

        session.delete(position)
        session.commit()

        logger.info(f"Position closed — {ticker} @ ${exit_price:.2f} | PnL: ${pnl:.2f}")
        return pnl
    except Exception as e:
        session.rollback()
        logger.error(f"Error closing position: {e}")
        return 0.0
    finally:
        session.close()


def update_position_price(ticker: str, current_price: float) -> None:
    session = get_session()
    try:
        position = session.query(Position).filter_by(ticker=ticker).first()
        if position:
            position.current_price = current_price
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating position price: {e}")
    finally:
        session.close()


def execute_trade(verdict: dict, config: dict) -> None:
    ticker = verdict["ticker"]
    direction = verdict["direction"]
    execution_mode = config["executor"]["execution_mode"]
    budget = config["executor"]["budget_per_trade"]
    max_positions = config["executor"]["max_open_positions"]
    daily_loss_limit = config["executor"]["daily_loss_limit"]
    stop_loss_pct = config["executor"]["stop_loss_pct"]
    take_profit_pct = config["executor"]["take_profit_pct"]

    logger.info(f"Executor processing — {ticker} | {direction} | mode: {execution_mode}")

    # risk guard
    daily_pnl = get_daily_pnl()
    if daily_pnl <= -daily_loss_limit:
        logger.warning(f"Daily loss limit reached (${daily_pnl:.2f}) — no new trades today")
        return

    open_count = get_open_position_count()
    if open_count >= max_positions:
        logger.warning(f"Max positions reached ({open_count}/{max_positions}) — skipping")
        return

    # check if position already exists
    session = get_session()
    try:
        existing = session.query(Position).filter_by(ticker=ticker).first()
        if existing:
            logger.info(f"Position already exists for {ticker} — skipping")
            return
    finally:
        session.close()

    current_price = get_stock_price(ticker)
    if not current_price:
        logger.warning(f"Could not get price for {ticker} — skipping")
        return

    risk_ceiling = calculate_risk_ceiling(open_count, max_positions, budget * max_positions)
    safe_size = verdict.get("safe_size", budget)
    position_size = calculate_position_size(budget, safe_size, risk_ceiling)

    if position_size <= 0:
        logger.warning(f"Position size is 0 for {ticker} — skipping")
        return

    stop_loss = calculate_stop_loss(current_price, stop_loss_pct)
    take_profit = calculate_take_profit(current_price, take_profit_pct)
    shares = position_size / current_price

    if execution_mode == "observe":
        logger.info(f"OBSERVE MODE — would buy {shares:.4f} shares of {ticker} @ ${current_price:.2f}")
        logger.info(f"  Position size: ${position_size:.2f}")
        logger.info(f"  Stop loss:     ${stop_loss:.2f} ({stop_loss_pct:.0%} below entry)")
        logger.info(f"  Take profit:   ${take_profit:.2f} ({take_profit_pct:.0%} above entry)")
        logger.info(f"  LLM reasoning: {verdict.get('llm_reasoning', 'N/A')}")

        trade_id = write_trade(
            verdict_id=verdict["verdict_id"],
            ticker=ticker,
            direction=direction,
            entry_price=current_price,
            size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            execution_mode="observe"
        )

        if trade_id:
            write_position(ticker, direction, position_size,
                          current_price, stop_loss, take_profit)

    elif execution_mode == "paper":
        logger.info(f"PAPER MODE — Alpaca paper trading not yet configured")

    elif execution_mode == "live":
        logger.info(f"LIVE MODE — Alpaca live trading not yet configured")


def check_open_positions(config: dict) -> None:
    positions = get_open_positions()
    if not positions:
        return

    logger.info(f"Checking {len(positions)} open positions")

    for position in positions:
        try:
            current_price = get_stock_price(position.ticker)
            if not current_price:
                continue
            time.sleep(0.5)

            update_position_price(position.ticker, current_price)

            unrealised_pnl = (current_price - position.entry_price) / position.entry_price * position.size
            logger.info(f"Position {position.ticker} — entry: ${position.entry_price:.2f} | current: ${current_price:.2f} | unrealised PnL: ${unrealised_pnl:.2f}")

            session = get_session()
            try:
                trade = session.query(Trade).filter_by(
                    ticker=position.ticker,
                    status="open"
                ).first()
                trade_id = trade.id if trade else None
            finally:
                session.close()

            if not trade_id:
                continue

            if check_stop_loss(current_price, position.stop_loss):
                logger.info(f"STOP LOSS triggered for {position.ticker} @ ${current_price:.2f}")
                close_position(position.ticker, current_price, trade_id)

            elif check_take_profit(current_price, position.take_profit):
                logger.info(f"TAKE PROFIT triggered for {position.ticker} @ ${current_price:.2f}")
                close_position(position.ticker, current_price, trade_id)

        except Exception as e:
            logger.warning(f"Error checking position {position.ticker}: {e}")
            continue


def run_executor_verdicts() -> None:
    from agents.analyst import analyse_signal
    config = load_config()
    verdicts = get_trade_verdicts()
    if not verdicts:
        logger.info("Executor — no new TRADE verdicts")
        return

    for verdict in verdicts:
        try:
            # check position limit before re-analysing
            open_count = get_open_position_count()
            if open_count >= config["executor"]["max_open_positions"]:
                logger.info(f"Max positions reached — stopping")
                break

            # re-run analyst on the signal before executing
            session = get_session()
            try:
                signal = session.query(Signal).filter_by(
                    id=verdict["signal_id"]
                ).first()
                if not signal:
                    continue
                signal_dict = {
                    "id": signal.id,
                    "trader_id": signal.trader_id,
                    "ticker": signal.ticker,
                    "signal_type": signal.signal_type,
                    "direction": signal.direction,
                    "size": signal.size,
                    "price_at_signal": signal.price_at_signal,
                    "source": signal.source,
                    "raw_data": json.loads(signal.raw_data) if signal.raw_data else {},
                    "timestamp": signal.timestamp
                }
            finally:
                session.close()

            logger.info(f"Re-analysing signal {signal.id} — {signal.ticker} before execution")
            fresh_verdict = analyse_signal(signal_dict, config)

            if fresh_verdict != "TRADE":
                logger.info(f"Signal {signal.id} re-analysis returned {fresh_verdict} — skipping")
                continue

            # fresh verdict is still TRADE — execute
            execute_trade(verdict, config)

        except Exception as e:
            logger.error(f"Error executing trade for {verdict['ticker']}: {e}")


def run_position_monitor() -> None:
    from datetime import datetime, timezone, timedelta

    # check if US market is open (9:30am - 4:00pm ET = 7:00pm - 1:30am IST)
    now_utc = datetime.now(timezone.utc)
    now_et_hour = (now_utc.hour - 4) % 24  # UTC-4 for EDT
    now_et_minute = now_utc.minute

    market_open = (now_et_hour == 9 and now_et_minute >= 30) or (10 <= now_et_hour <= 15)

    if not market_open:
        # market closed — no point fetching prices
        return
    config = load_config()
    check_open_positions(config)
    logger.info("Position monitor complete")


def run_executor() -> None:
    logger.info("Executor starting")
    config = load_config()
    init_db()

    check_open_positions(config)

    open_count = get_open_position_count()
    if open_count >= config["executor"]["max_open_positions"]:
        logger.info(f"Max positions reached ({open_count}) — no new trades")
        return

    run_executor_verdicts()
    logger.info("Executor run complete")


if __name__ == "__main__":
    run_executor()