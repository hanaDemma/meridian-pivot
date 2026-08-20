"""
api/app.py

Day 3 original spec: expose a query endpoint over the cached stock.

Runs the poller as a background thread inside this same process, so
it shares the in-memory cache with the query endpoints below. This
is the "support tool" side of the system — Northstar's support agents
hit this to answer "is this in stock?" without ever touching the
warehouse system directly.

Run: python3 api/app.py   (port 7001)
Set POLL_INTERVAL_SECONDS=5 for fast local testing instead of the
real 300s spec value.
"""

import os
import sys
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from cache.stock_cache import get_stock, get_all_stock, last_updated
from polling.poller import run_forever

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/stock/<sku>", methods=["GET"])
def query_stock(sku):
    qty = get_stock(sku)
    if qty is None:
        return jsonify({"status": "error", "reason": "unknown SKU or cache not yet populated"}), 404
    return jsonify({"sku": sku, "quantity": qty, "cache_last_updated": last_updated()}), 200


@app.route("/stock", methods=["GET"])
def query_all_stock():
    return jsonify({"stock": get_all_stock(), "cache_last_updated": last_updated()}), 200


if __name__ == "__main__":
    poller_thread = threading.Thread(target=run_forever, daemon=True)
    poller_thread.start()
    app.run(port=7001, debug=False)