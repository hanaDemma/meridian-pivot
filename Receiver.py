"""
Day 1-2 Solo Mini-Prototype — Webhook Verification
Receives stock-update webhooks and verifies each one is genuinely from
Northstar Retail Co. (not spoofed) before trusting the payload.
"""

import hmac
import hashlib
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# In real deployment this is a shared secret only Northstar and we know.
# Never hardcode in production — env var / secrets manager instead.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "dev-secret-change-me")

# in-memory stock cache — stands in for a real DB/Redis in this prototype
stock_cache = {}


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Recompute the HMAC-SHA256 signature over the raw request body using
    the shared secret, and compare it to the signature the sender attached.
    Using compare_digest (not ==) to avoid timing-attack leakage.
    """
    if not signature_header:
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.route("/webhook", methods=["POST"])
def webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-Signature")

    if not verify_signature(raw_body, signature):
        # Deliberately vague error — don't tell an attacker *why* it failed
        return jsonify({"error": "invalid signature"}), 401

    data = request.get_json(silent=True)
    if not data or "product_id" not in data or "quantity" not in data:
        return jsonify({"error": "missing product_id or quantity"}), 400

    product_id = data["product_id"]
    quantity = data["quantity"]
    stock_cache[product_id] = quantity

    print(f"[verified] product={product_id} qty={quantity}")
    return jsonify({"status": "received", "product_id": product_id}), 200


@app.route("/stock/<product_id>", methods=["GET"])
def get_stock(product_id):
    if product_id not in stock_cache:
        return jsonify({"error": "unknown product"}), 404
    return jsonify({"product_id": product_id, "quantity": stock_cache[product_id]})


if __name__ == "__main__":
    app.run(port=5000, debug=False)