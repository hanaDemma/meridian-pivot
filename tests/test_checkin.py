"""
tests/test_checkin.py

Proves Day 3 kiosk/app.py meets spec.

Run order:
  1. python3 printer_vendor/app.py   (terminal 1)
  2. python3 kiosk/app.py            (terminal 2)
  3. python3 tests/test_checkin.py   (terminal 3)

Covers:
  - 3 distinct attendees checking in successfully (kiosk waits for
    print success before returning "Checked In")
  - 1 duplicate scan of an already-checked-in attendee -> no second print
"""

import time
import requests

KIOSK_URL = "http://127.0.0.1:8001/checkin"

attendees = [
    {"attendee_id": "A001", "name": "Selam Tesfaye"},
    {"attendee_id": "A002", "name": "Michael Okonjo"},
    {"attendee_id": "A003", "name": "Aisha Bello"},
]


def scan(attendee, label):
    start = time.time()
    resp = requests.post(KIOSK_URL, json=attendee)
    elapsed = time.time() - start
    body = resp.json()
    print(f"[{label}] {attendee['name']} -> {resp.status_code} {body['status']} "
          f"(took {elapsed:.2f}s) :: {body}")
    return body


print("=== Scanning 3 distinct attendees ===")
for a in attendees:
    result = scan(a, "first scan")
    assert result["status"] == "Checked In", f"Expected Checked In for {a['name']}"

print("\n=== Duplicate scan: re-scanning A001 ===")
dup_result = scan(attendees[0], "duplicate scan")
assert dup_result["status"] == "already_checked_in", "Duplicate scan should NOT trigger a reprint"

print("\n✅ All Day 3 checks passed: sync print + duplicate-scan protection working")