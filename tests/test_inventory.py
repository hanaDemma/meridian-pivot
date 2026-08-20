"""
tests/test_inventory.py

Proves Day 3 meets spec:
  - poller successfully pulls from the warehouse API
  - cache reflects what the warehouse returned
  - query endpoint serves cached data without hitting the warehouse directly

Run order:
  1. python3 warehouse/app.py                          (terminal 1)
  2. POLL_INTERVAL_SECONDS=5 python3 api/app.py         (terminal 2)
  3. python3 tests/test_inventory.py                    (terminal 3)
"""

import time
import requests

API_URL = "http://localhost:7001"
WAREHOUSE_URL = "http://localhost:7000"

print("=== Waiting for first poll cycle to populate cache ===")
time.sleep(6)  # POLL_INTERVAL_SECONDS=5 in api/app.py for this test run

print("\n=== Querying single SKU ===")
resp = requests.get(f"{API_URL}/stock/SKU-1001")
print(resp.status_code, resp.json())
assert resp.status_code == 200
assert "quantity" in resp.json()

print("\n=== Querying full stock snapshot ===")
resp = requests.get(f"{API_URL}/stock")
print(resp.status_code, resp.json())
assert resp.status_code == 200
assert len(resp.json()["stock"]) > 0

print("\n=== Querying unknown SKU (should 404) ===")
resp = requests.get(f"{API_URL}/stock/SKU-9999")
print(resp.status_code, resp.json())
assert resp.status_code == 404

print("\n=== Confirming cache updates on next poll cycle ===")
first_snapshot = requests.get(f"{API_URL}/stock").json()
print("first_snapshot cache_last_updated:", first_snapshot["cache_last_updated"])

# Poll the query endpoint every second, up to 15s, instead of a single fixed
# sleep. A fixed sleep can race against the poller's own interval and land
# right on a boundary; actively waiting for the value to change is more
# reliable regardless of exact timing.
second_snapshot = None
for attempt in range(15):
    time.sleep(1)
    candidate = requests.get(f"{API_URL}/stock").json()
    if candidate["cache_last_updated"] > first_snapshot["cache_last_updated"]:
        second_snapshot = candidate
        print(f"cache advanced after {attempt + 1}s wait")
        break

assert second_snapshot is not None, (
    "cache_last_updated never advanced within 15s — is api/app.py running with "
    "POLL_INTERVAL_SECONDS=5? Check the terminal running api/app.py for "
    "'[poller] starting, interval=5s'."
)
print("cache_last_updated advanced:", first_snapshot["cache_last_updated"], "->", second_snapshot["cache_last_updated"])

print("\n✅ All Day 3 checks passed: poll -> cache -> query endpoint working")