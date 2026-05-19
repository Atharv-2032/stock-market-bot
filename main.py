from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from agents.scout import run_scout
from agents.watchdog import run_watchdog
from agents.analyst import run_analyst
from agents.executor import run_executor_verdicts, run_position_monitor, get_open_positions, get_daily_pnl
from database.db import init_db, get_session, Trade, Position
from utils.config import load_config
from utils.logger import logger
from datetime import datetime, timezone


def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} crashed: {event.exception}")


def is_market_open() -> bool:
    now_utc = datetime.now(timezone.utc)
    # market closed on weekends
    if now_utc.weekday() >= 5:
        return False
    now_et_hour = (now_utc.hour - 4) % 24
    now_et_minute = now_utc.minute
    # market open 9:30am - 4:00pm ET
    after_open = (now_et_hour == 9 and now_et_minute >= 30) or (now_et_hour >= 10)
    before_close = now_et_hour < 16
    return after_open and before_close


def pnl_report() -> None:
    session = get_session()
    try:
        # realised PnL
        closed_trades = session.query(Trade).filter_by(status="closed").all()
        realised_pnl = sum(t.pnl for t in closed_trades)
        winning = [t for t in closed_trades if t.pnl > 0]
        losing = [t for t in closed_trades if t.pnl < 0]

        # unrealised PnL
        positions = session.query(Position).all()
        unrealised_pnl = sum(
            (p.current_price - p.entry_price) / p.entry_price * p.size
            for p in positions
        )

        logger.info("=" * 50)
        logger.info("P&L REPORT")
        logger.info("=" * 50)
        logger.info(f"Open positions:     {len(positions)}")
        logger.info(f"Closed trades:      {len(closed_trades)}")
        logger.info(f"  Winners:          {len(winning)}")
        logger.info(f"  Losers:           {len(losing)}")
        if closed_trades:
            win_rate = len(winning) / len(closed_trades) * 100
            logger.info(f"  Win rate:         {win_rate:.1f}%")
        logger.info(f"Realised PnL:       ${realised_pnl:.2f}")
        logger.info(f"Unrealised PnL:     ${unrealised_pnl:.2f}")
        logger.info(f"Total PnL:          ${realised_pnl + unrealised_pnl:.2f}")

        if positions:
            logger.info("Open positions:")
            for p in positions:
                pnl = (p.current_price - p.entry_price) / p.entry_price * p.size
                logger.info(f"  {p.ticker} | entry:${p.entry_price:.2f} | current:${p.current_price:.2f} | PnL:${pnl:.2f}")

        if closed_trades:
            logger.info("Closed trades:")
            for t in closed_trades:
                logger.info(f"  {t.ticker} | entry:${t.entry_price:.2f} | exit:${t.exit_price:.2f} | PnL:${t.pnl:.2f}")

        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error generating PnL report: {e}")
    finally:
        session.close()


def run_watchdog_pipeline():
    if not is_market_open():
        logger.info("Market closed — skipping pipeline")
        return

    logger.info("Pipeline starting")
    signals_fired = run_watchdog()

    if signals_fired > 0:
        logger.info(f"Pipeline — {signals_fired} signals detected, running Analyst")
        verdicts = run_analyst()

        if verdicts.get("TRADE", 0) > 0:
            logger.info(f"Pipeline — {verdicts['TRADE']} TRADE verdicts, running Executor")
            run_executor_verdicts()
    else:
        logger.info("Pipeline — no signals detected")

    logger.info("Pipeline complete")


def main():
    logger.info("Starting Multi-Agent Trading System")
    config = load_config()
    init_db()

    scheduler = BlockingScheduler()
    scheduler.add_listener(job_listener, EVENT_JOB_ERROR)

    # scout — every 4 hours regardless of market hours
    scheduler.add_job(
        run_scout,
        'interval',
        hours=config["scout"]["run_interval_hours"],
        id='scout',
        name='Scout',
        max_instances=1
    )

    # pipeline — every 3 minutes, only runs during market hours
    scheduler.add_job(
        run_watchdog_pipeline,
        'interval',
        seconds=config["watchdog"]["poll_interval_seconds"],
        id='pipeline',
        name='Pipeline',
        max_instances=1
    )

    # position monitor — every 30 seconds, market hours check is inside the function
    scheduler.add_job(
        run_position_monitor,
        'interval',
        seconds=30,
        id='position_monitor',
        name='Position Monitor',
        max_instances=1
    )

    # pnl report — every 2 hours
    scheduler.add_job(
        pnl_report,
        'interval',
        hours=2,
        id='pnl_report',
        name='PnL Report',
        max_instances=1
    )

    logger.info("Scheduler configured:")
    logger.info(f"  Scout          → every {config['scout']['run_interval_hours']} hours")
    logger.info(f"  Pipeline       → every {config['watchdog']['poll_interval_seconds']}s (market hours only)")
    logger.info(f"  Position monitor → every 30s (market hours only)")
    logger.info(f"  PnL report     → every 2 hours")

    # startup sequence
    logger.info("Running startup sequence")

    try:
        run_scout()
    except Exception as e:
        logger.error(f"Scout startup error: {e}")

    if is_market_open():
        try:
            run_watchdog_pipeline()
        except Exception as e:
            logger.error(f"Pipeline startup error: {e}")
    else:
        logger.info("Market closed — skipping startup pipeline")

    # always run position monitor and pnl report on startup
    try:
        run_position_monitor()
    except Exception as e:
        logger.error(f"Position monitor startup error: {e}")

    pnl_report()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("System stopped by user")
        pnl_report()
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    main()