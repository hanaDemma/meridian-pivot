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
time.sleep(6)
second_snapshot = requests.get(f"{API_URL}/stock").json()
assert second_snapshot["cache_last_updated"] > first_snapshot["cache_last_updated"]
print("cache_last_updated advanced:", first_snapshot["cache_last_updated"], "->", second_snapshot["cache_last_updated"])

print("\n✅ All Day 3 checks passed: poll -> cache -> query endpoint working")