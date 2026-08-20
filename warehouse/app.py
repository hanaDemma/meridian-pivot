"""
warehouse/app.py

Stands in for Northstar Retail Co.'s warehouse stock system.
This is the vendor's REST API our service polls every 5 minutes
(Day 3 original spec). On Day 4 this same endpoint is what the
webhook push model replaces polling for.

Run: python3 warehouse/app.py   (port 7000)
"""

import random
import time
from flask import Flask, jsonify

app = Flask(__name__)

# Seed stock levels for a handful of SKUs. Levels drift slightly on
# each poll to simulate a real warehouse (sales, restocks happening
# independently of our service).
_stock = {
    "SKU-1001": 42,
    "SKU-1002": 7,
    "SKU-1003": 0,
    "SKU-1004": 130,
}


@app.route("/warehouse/stock", methods=["GET"])
def get_all_stock():
    # Simulate minor real-world drift between polls
    for sku in _stock:
        drift = random.choice([-1, 0, 0, 1])
        _stock[sku] = max(0, _stock[sku] + drift)

    return jsonify({
        "timestamp": time.time(),
        "stock": _stock,
    }), 200


@app.route("/warehouse/stock/<sku>", methods=["GET"])
def get_one_stock(sku):
    if sku not in _stock:
        return jsonify({"status": "error", "reason": "unknown SKU"}), 404
    return jsonify({"sku": sku, "quantity": _stock[sku], "timestamp": time.time()}), 200


if __name__ == "__main__":
    app.run(port=7000, debug=False)