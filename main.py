from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from agents.scout import run_scout
from agents.watchdog import run_watchdog
from agents.analyst import run_analyst
from agents.executor import run_executor_verdicts, run_position_monitor
from database.db import init_db
from utils.config import load_config
from utils.logger import logger


def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} crashed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} completed")


def run_watchdog_pipeline():
    logger.info("Pipeline starting")

    # step 1 — watchdog detects signals
    signals_fired = run_watchdog()

    # step 2 — analyst processes signals immediately if any fired
    if signals_fired > 0:
        logger.info(f"Pipeline — {signals_fired} signals detected, running Analyst")
        verdicts = run_analyst()

        # step 3 — executor processes TRADE verdicts immediately
        if verdicts.get("TRADE", 0) > 0:
            logger.info(f"Pipeline — {verdicts['TRADE']} TRADE verdicts, running Executor")
            run_executor_verdicts()
    else:
        logger.info("Pipeline — no signals detected, skipping Analyst and Executor")

    logger.info("Pipeline complete")


def main():
    logger.info("Starting Multi-Agent Trading System")
    config = load_config()
    init_db()

    scheduler = BlockingScheduler()
    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    # scout — every 4 hours
    scheduler.add_job(
        run_scout,
        'interval',
        hours=config["scout"]["run_interval_hours"],
        id='scout',
        name='Scout',
        max_instances=1
    )

    # watchdog pipeline — every 3 minutes
    # watchdog → analyst → executor (chained, only runs if signals exist)
    scheduler.add_job(
        run_watchdog_pipeline,
        'interval',
        seconds=config["watchdog"]["poll_interval_seconds"],
        id='pipeline',
        name='Pipeline',
        max_instances=1
    )

    # position monitor — every 30 seconds independently
    # monitors stop loss and take profit regardless of new signals
    scheduler.add_job(
        run_position_monitor,
        'interval',
        seconds=30,
        id='position_monitor',
        name='Position Monitor',
        max_instances=1
    )

    logger.info("Scheduler configured:")
    logger.info(f"  Scout            → every {config['scout']['run_interval_hours']} hours")
    logger.info(f"  Watchdog pipeline → every {config['watchdog']['poll_interval_seconds']} seconds")
    logger.info(f"    → Analyst runs only when signals detected")
    logger.info(f"    → Executor runs only when TRADE verdicts exist")
    logger.info(f"  Position monitor  → every 30 seconds")
    logger.info("Press Ctrl+C to stop")

    # startup sequence — run everything once immediately
    logger.info("Running startup sequence")

    try:
        run_scout()
    except Exception as e:
        logger.error(f"Scout startup error: {e}")

    try:
        run_watchdog_pipeline()
    except Exception as e:
        logger.error(f"Pipeline startup error: {e}")

    try:
        run_position_monitor()
    except Exception as e:
        logger.error(f"Position monitor startup error: {e}")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("System stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    main()