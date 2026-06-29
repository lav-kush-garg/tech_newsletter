"""
Scheduler
==========
Runs the newsletter pipeline at the times configured in settings.py.

Usage:
  python scheduler.py              → start scheduler (runs indefinitely)
  python scheduler.py --run-now   → run once immediately then schedule

Times are configured in config/settings.py → SCHEDULE_TIMES
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import schedule

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from config.settings import SCHEDULE_TIMES, TIMEZONE
from pipeline import run_pipeline


def _run_job():
    local_now = datetime.now(ZoneInfo(TIMEZONE))
    logger.info(f"⏰ Scheduled run triggered at {local_now.strftime('%H:%M %Z')}")
    try:
        run_pipeline()
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)


def start_scheduler(run_now: bool = False):
    logger.info(f"📅 Scheduler starting. Timezone: {TIMEZONE}")
    logger.info(f"   Scheduled times: {', '.join(SCHEDULE_TIMES)}")

    for t in SCHEDULE_TIMES:
        schedule.every().day.at(t).do(_run_job)
        logger.info(f"   Registered: daily at {t} {TIMEZONE}")

    if run_now:
        logger.info("Running immediately (--run-now flag)...")
        _run_job()

    logger.info("Scheduler running. Press Ctrl+C to stop.\n")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Newsletter Scheduler")
    parser.add_argument("--run-now", action="store_true", help="Run immediately then schedule")
    args = parser.parse_args()
    start_scheduler(run_now=args.run_now)
