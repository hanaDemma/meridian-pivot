
# meridian-pivot

The Meridian Pivot sprint — Northstar Retail Co. inventory sync service.

This repo covers the full sprint in one continuous history: Day 1–2 solo
tool recon, Day 3 original spec, and the Day 4 pivot (webhook push model)
once it lands. Nothing from before the pivot gets deleted — obsolete code
is marked deprecated in place, per the sprint's non-negotiable rules.

---

## Day 1–2 — Assignment 1: Solo Mini-Prototype (Webhook Verification)

### What this is

A minimal proof that a webhook receiver can tell a **genuine** stock-update
push (from "Northstar Retail Co.") apart from a **spoofed or tampered** one,
using HMAC-SHA256 signature verification.

### Why this tool

Assigned/chosen because I'd never implemented webhook signature verification
before. It matters for the Meridian Pivot because Day 4's pivot moves the
whole project from *polling* a warehouse API to *receiving* pushed webhook
events — at that point, anyone who finds the endpoint URL could POST fake
stock data unless the receiver checks *who* actually sent it.

### Files

- `Receiver.py` — Flask webhook endpoint with signature verification +
  a `/stock/<product_id>` query endpoint
- `Sender.py` — test harness that sends a valid request, a tampered request,
  and a request with no signature, to prove the check actually works
- `LEARNING_BLOCKER_JOURNAL.md` — blockers faced and how they were resolved
- `logs/` — output from the live runs used to verify this prototype

### How to run

```bash
pip install flask requests
python3 Receiver.py            # terminal 1
python3 Sender.py              # terminal 2
```

### Verified behavior

| Case                                | Expected                                     | Actual       |
| ----------------------------------- | -------------------------------------------- | ------------ |
| Valid signature                     | 200, stock updated                           | ✅ 200       |
| Tampered payload w/ stale signature | 401, rejected                                | ✅ 401       |
| No signature header                 | 401, rejected                                | ✅ 401       |
| Query endpoint after valid push     | Returns correct stored value (42, not 99999) | ✅ confirmed |

### What I'd add with more time

- Timestamp + nonce in the signed payload, to prevent replay attacks
- Real persistence (Redis/DB) instead of the in-memory dict
- Rate limiting on the endpoint

---

## Day 3 — Original Spec: Warehouse Inventory Sync

### What this is

Northstar's original requirement: poll a warehouse API every 5 minutes,
cache the stock levels, and expose a query endpoint so the support tool's
"is this in stock?" answers stay accurate — without hitting the warehouse
system directly on every question.

This is the **"before" state** that Day 4 pivots away from. `polling/` is
the piece that gets killed once the client announces the switch to a
webhook push model — kept intact here as the baseline for the Scope Delta
Analysis.

### Files

- `warehouse/app.py` — mock warehouse vendor API (simulates Northstar's
  stock system, port 7000)
- `polling/poller.py` — polls the warehouse every `POLL_INTERVAL_SECONDS`
  (default 300s / 5 min) and writes results into the cache
- `cache/stock_cache.py` — thread-safe in-memory cache shared between the
  poller (writer) and the query API (reader)
- `api/app.py` — runs the poller in a background thread and exposes
  `GET /stock/<sku>` and `GET /stock` (port 7001)
- `tests/test_inventory.py` — automated check: single-SKU query, full
  snapshot query, unknown-SKU 404, and confirmation that the cache
  actually advances between poll cycles
- `requirements.txt`

### How to run

```bash
pip install -r requirements.txt

# terminal 1
python3 warehouse/app.py

# terminal 2 — short interval for local testing (real spec value is 300)
POLL_INTERVAL_SECONDS=5 python3 api/app.py

# terminal 3
python3 tests/test_inventory.py
```

### Verified behavior

| Case                                | Expected                                       | Actual       |
| ----------------------------------- | ---------------------------------------------- | ------------ |
| Query known SKU                     | 200, correct quantity                          | ✅ 200       |
| Query full stock snapshot           | 200, all SKUs present                          | ✅ 200       |
| Query unknown SKU                   | 404                                            | ✅ 404       |
| Cache reflects fresh poll over time | `cache_last_updated` advances between cycles | ✅ confirmed |

### Notable blocker (see Learning & Blocker Journal for full writeup)

Test intermittently failed with `cache_last_updated never advanced`, traced
to two separate causes: a stale `api/app.py` process left running on port
7001 from an earlier session, and a PowerShell env var (`$env:POLL_INTERVAL_SECONDS`)
not persisting across terminal windows. Fixed by killing the orphaned
process and rewriting the test to actively wait for the value to change
instead of relying on a single fixed sleep, which also removed a latent
race condition.

---

## Day 4 — The Pivot

*(in progress)*

---

## Non-negotiable rules this repo follows

- Obsolete code from before the pivot is marked deprecated, not deleted or
  left running in parallel.
- Same repo, same commit history, start to finish — no separate repo per day.
