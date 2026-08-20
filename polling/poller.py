"""
polling/poller.py

Day 3 original spec: poll the warehouse API every 5 minutes and
cache stock.

POLL_INTERVAL_SECONDS defaults to 300 (5 min) per spec, but is
overridable via env var so it can be tested quickly without waiting
5 minutes for every test run.

This is the exact piece Day 4 kills: "the polling method is being
killed in 48 hours - switch to a webhook push model instead."
Keep this module intact (don't delete it after the pivot) — mark it
deprecated instead, per the non-negotiable rules.
"""

import os
import sys
import time
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from cache.stock_cache import update_stock

WAREHOUSE_URL = "http://localhost:7000/warehouse/stock"
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", 300))


def poll_once():
    try:
        resp = requests.get(WAREHOUSE_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        update_stock(data["stock"])
        print(f"[poller] cache updated: {data['stock']}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[poller] poll failed: {e}")
        return False


def run_forever():
    print(f"[poller] starting, interval={POLL_INTERVAL_SECONDS}s")
    while True:
        poll_once()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()