from apscheduler.schedulers.blocking import BlockingScheduler
from agents.watchdog import run_watchdog
from agents.analyst import run_analyst
from utils.logger import logger

scheduler = BlockingScheduler()

# run watchdog every 3 minutes
scheduler.add_job(
    run_watchdog,
    'interval',
    minutes=3,
    id='watchdog',
    name='Watchdog'
)

# run analyst every 30 seconds
scheduler.add_job(
    run_analyst,
    'interval',
    seconds=30,
    id='analyst',
    name='Analyst'
)

logger.info("Starting Watchdog + Analyst scheduler")
logger.info("Watchdog runs every 3 minutes")
logger.info("Analyst runs every 30 seconds")
logger.info("Press Ctrl+C to stop")

try:
    scheduler.start()
except KeyboardInterrupt:
    logger.info("Scheduler stopped")