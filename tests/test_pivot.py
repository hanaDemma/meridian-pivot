"""
tests/test_pivot.py — Day 4

Proves the pivot actually works, not just that the old test still
passes. Covers everything the spec calls out specifically:

  1. POST /checkin returns "pending" almost immediately (NOT "Checked
     In", and NOT after waiting ~1.5s like Day 3 — that's the whole
     point of the pivot).
  2. GET /status/<id> eventually flips to "checked_in" once the
     vendor's webhook fires, proving the async round trip works.
  3. Duplicate scan WHILE pending doesn't queue a second print job.
  4. Duplicate scan AFTER checked_in still returns
     "already_checked_in", same as Day 3.
  5. A duplicated/out-of-order webhook redelivery for the same job_id
     is handled idempotently — sending the exact same signed webhook
     twice must not error or double-process on the second call.
  6. An unsigned/tampered webhook is rejected with 401 — the receiver
     actually checks the signature, it doesn't just trust any POST.

Run order:
  1. python3 printer_vendor/app.py   (terminal 1)
  2. python3 kiosk/app.py            (terminal 2)
  3. python3 tests/test_pivot.py     (terminal 3)
"""

import hashlib
import hmac
import json
import time
import requests

KIOSK_URL = "http://127.0.0.1:8001"
WEBHOOK_SECRET = b"solstice-shared-secret-change-me"  # must match kiosk/app.py

attendees = [
    {"attendee_id": "B001", "name": "Selam Tesfaye"},
    {"attendee_id": "B002", "name": "Michael Okonjo"},
    {"attendee_id": "B003", "name": "Aisha Bello"},
]


def sign(raw_bytes):
    return hmac.new(WEBHOOK_SECRET, raw_bytes, hashlib.sha256).hexdigest()


def poll_until_checked_in(attendee_id, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{KIOSK_URL}/status/{attendee_id}")
        if resp.json().get("status") == "checked_in":
            return time.time() - start
        time.sleep(0.3)
    return None


print("=== 1. Scanning 3 attendees — should return 'pending' almost instantly ===")
job_ids = {}
for a in attendees:
    start = time.time()
    resp = requests.post(f"{KIOSK_URL}/checkin", json=a)
    elapsed = time.time() - start
    body = resp.json()
    print(f"{a['name']} -> {resp.status_code} {body['status']} (took {elapsed:.2f}s)")
    assert resp.status_code == 202, "Expected 202 Accepted, not a blocking 200"
    assert body["status"] == "pending", "Should be pending, not 'Checked In' — that's the whole pivot"
    assert elapsed < 1.0, f"checkin should return almost immediately now, took {elapsed:.2f}s"
    job_ids[a["attendee_id"]] = body["job_id"]

print("\n=== 2. Duplicate scan WHILE pending — should NOT queue a second print ===")
dup = requests.post(f"{KIOSK_URL}/checkin", json=attendees[0]).json()
assert dup["status"] == "pending"
assert dup["job_id"] == job_ids["B001"], "Should reference the SAME job, not a new one"
print(f"Duplicate scan while pending correctly returned same job_id: {dup['job_id']}")

print("\n=== 3. Waiting for webhook confirmations (async, may arrive out of order) ===")
for a in attendees:
    wait_time = poll_until_checked_in(a["attendee_id"])
    assert wait_time is not None, f"{a['name']} never reached checked_in within timeout"
    print(f"{a['name']} confirmed checked_in after {wait_time:.2f}s")

print("\n=== 4. Duplicate scan AFTER checked_in — should say already_checked_in ===")
dup2 = requests.post(f"{KIOSK_URL}/checkin", json=attendees[0]).json()
assert dup2["status"] == "already_checked_in"
print(f"Post-completion duplicate scan correctly rejected: {dup2}")

print("\n=== 5. Simulating a duplicate/out-of-order webhook redelivery ===")
body = {"job_id": job_ids["B002"], "attendee_id": "B002", "status": "success"}
raw = json.dumps(body).encode("utf-8")
sig = sign(raw)
resp = requests.post(
    f"{KIOSK_URL}/webhook/print-complete",
    data=raw,
    headers={"Content-Type": "application/json", "X-Signature": sig},
)
assert resp.status_code == 200
assert resp.json()["status"] == "already_processed", "Redelivery should be a safe no-op"
print(f"Redelivered webhook handled idempotently: {resp.json()}")

print("\n=== 6. Rejecting an unsigned webhook ===")
resp = requests.post(
    f"{KIOSK_URL}/webhook/print-complete",
    data=raw,
    headers={"Content-Type": "application/json"},  # no X-Signature
)
assert resp.status_code == 401
print(f"Unsigned webhook correctly rejected: {resp.status_code}")

print("\n✅ All Day 4 pivot checks passed: async checkin, webhook completion, "
      "idempotent duplicate handling, and signature verification all working")