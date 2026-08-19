"""
Test harness for the webhook receiver.
Sends three requests:
  1. A correctly signed request  -> should succeed (200)
  2. A tampered payload with the old signature -> should fail (401)
  3. A request with no signature at all -> should fail (401)

This is what proves the verification logic actually works, not just
that the endpoint exists.
"""

import hmac
import hashlib
import json
import requests

WEBHOOK_SECRET = "my-secret"  # must match receiver.py
URL = "http://localhost:5000/webhook"


def sign(body_bytes: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()


def send(payload: dict, tamper_after_signing=False, drop_signature=False, label=""):
    body = json.dumps(payload).encode()
    signature = sign(body)

    if tamper_after_signing:
        # attacker-style edit: change quantity after signature was computed
        payload["quantity"] = 99999
        body = json.dumps(payload).encode()

    headers = {"Content-Type": "application/json"}
    if not drop_signature:
        headers["X-Signature"] = signature

    resp = requests.post(URL, data=body, headers=headers)
    print(f"--- {label} ---")
    print(f"status: {resp.status_code}  body: {resp.text}")
    print()


if __name__ == "__main__":
    send(
        {"product_id": "SKU-001", "quantity": 42},
        label="1. Valid signed request (expect 200)",
    )

    send(
        {"product_id": "SKU-001", "quantity": 42},
        tamper_after_signing=True,
        label="2. Tampered payload, stale signature (expect 401)",
    )

    send(
        {"product_id": "SKU-001", "quantity": 42},
        drop_signature=True,
        label="3. No signature header at all (expect 401)",
    )