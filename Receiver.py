"""
Day 1-2 Solo Mini-Prototype — Webhook Verification
Receives stock-update webhooks and verifies each one is genuinely from
Northstar Retail Co. (not spoofed) before trusting the payload.
"""

import hashlib
import hmac

from flask import Flask, jsonify, request

app = Flask(__name__)
WEBHOOK_SECRET = "my-secret"  # For local testing only; use an environment variable in production.
stock_cache = {}


def sign(secret: str, body_bytes: bytes) -> str:
    return hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str, body_bytes: bytes, received_signature: str | None
) -> bool:
    if not received_signature:
        return False

    computed_signature = sign(secret, body_bytes)
    return hmac.compare_digest(computed_signature, received_signature)


@app.route("/webhook", methods=["POST"])
def webhook():
    raw_body = request.get_data()
    received_signature = request.headers.get("X-Signature")

    if not verify_signature(WEBHOOK_SECRET, raw_body, received_signature):
        return jsonify({"error": "invalid signature"}), 401

    data = request.get_json(silent=True)
    if (
        not isinstance(data, dict)
        or "product_id" not in data
        or "quantity" not in data
    ):
        return jsonify({"error": "missing product_id or quantity"}), 400

    product_id = data["product_id"]
    quantity = data["quantity"]
    stock_cache[product_id] = quantity

    return jsonify({"status": "received", "product_id": product_id}), 200


@app.route("/stock/<product_id>", methods=["GET"])
def get_stock(product_id):
    if product_id not in stock_cache:
        return jsonify({"error": "unknown product"}), 404
    return jsonify({"product_id": product_id, "quantity": stock_cache[product_id]})


if __name__ == "__main__":
    app.run(port=5000, debug=False)


