"""
Weekly scheduler — runs every Sunday at 6am to pick up Saturday fight results.

Usage: python scraper/scheduler.py
"""

import schedule
import time
import sys

sys.path.insert(0, ".")

from scraper.run import run


def job():
    print("Running incremental scrape...")
    run(incremental=True)


# Every Sunday at 06:00
schedule.every().sunday.at("06:00").do(job)

if __name__ == "__main__":
    print("Scheduler running. Next job:", schedule.next_run())
    while True:
        schedule.run_pending()
        time.sleep(60)
