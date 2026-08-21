# meridian-pivot

The Meridian Pivot sprint — solo submission.

This repo covers the full sprint in one continuous history. Nothing
from before the pivot gets deleted — obsolete code is marked
deprecated in place, per the sprint's non-negotiable rules.

**Real client scenario (confirmed via the actual Day 4 pivot
document):** Solstice Events Co. — an event check-in kiosk service.
See `printer_vendor/`, `kiosk/`, `state/`, and
`tests/test_checkin.py` / `tests/test_pivot.py` below.

**Note on `warehouse/`, `polling/`, `cache/`, `api/`,
`tests/test_inventory.py`:** these were built against the *generic
example scenario* from the program's overview document (Northstar
Retail Co., warehouse polling), before the actual personally-assigned
pivot document was confirmed to be the Solstice kiosk scenario
instead. Left in the repo as-is — working, tested code, just built
against the wrong client story. Kept as honest evidence of a real
misunderstanding, caught and corrected, rather than removed.

---

## Day 1–2 — Assignment 1: Solo Mini-Prototype (Webhook Verification)

### What this is

A minimal proof that a webhook receiver can tell a **genuine** stock-update
push (from "Northstar Retail Co.") apart from a **spoofed or tampered** one,
using HMAC-SHA256 signature verification.

### Why this tool

Assigned/chosen because I'd never implemented webhook signature verification
before. It turned out to matter directly for Day 4 — the pivot moves
the whole project from a synchronous request/response call to
*receiving* pushed webhook events — at that point, anyone who finds
the endpoint URL could POST fake data unless the receiver checks
*who* actually sent it. That exact technique is reused in
`kiosk/app.py`'s webhook receiver.

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

## Day 3 (misdirected attempt) — Warehouse Inventory Sync

### What this is

Built against the generic program-overview scenario (Northstar
Retail Co.) before the real, personally-assigned pivot document was
confirmed to describe a different client entirely. Kept for
transparency, not deleted.

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

## Day 3 (correct) — Solstice Kiosk, Original Spec

### What this is

Solstice's actual requirement: when staff scan an attendee's QR code,
the kiosk calls the venue's badge-printer vendor **synchronously**,
waits for the print job to succeed, and only then shows
"Checked In." Duplicate scans of an already-checked-in attendee must
not trigger a second print.

This is the **"before" state** Day 4 pivots away from.

### Files

- `printer_vendor/app.py` *(Day 3 version, later overwritten — see
  git history / `feature/day3-solstice-original` branch)* — mock
  badge-printer vendor, synchronous `POST /print`
- `kiosk/app.py` *(Day 3 version, later overwritten)* — blocking
  check-in call + duplicate protection
- `state/checkin_state.py` *(Day 3 version, later overwritten)* —
  simple `attendee_id → job_id` map
- `tests/test_checkin.py` — 3 attendees + 1 duplicate scan, verified passing

### Verified behavior

| Case            | Expected                                     | Actual       |
| --------------- | -------------------------------------------- | ------------ |
| First-time scan | Blocks ~1.5s, then 200 "Checked In"          | ✅ confirmed |
| Duplicate scan  | Instant 200 "already_checked_in", no reprint | ✅ confirmed |

### Notable blockers

- Windows resolved `localhost` slowly (IPv6-first fallback), adding
  ~2-5s of pure network overhead to every call regardless of actual
  logic — diagnosed by noticing even the duplicate-scan case (which
  makes zero downstream calls) was still slow. Fixed by switching all
  URLs to `127.0.0.1`.
- A copy-paste mistake overwrote `state/checkin_state.py` with test
  code instead of the state module, causing a confusing import-time
  crash — diagnosed by reading the traceback line-by-line and noticing
  the file's line numbers didn't match what should be in it.

---

## Day 4 — The Pivot: Async Queue + Webhook

### What changed and why

Solstice's badge-printer vendor deprecated the synchronous print API,
no deadline extension. Spec required:

- Publish print requests to the vendor's queue instead of calling it synchronously
- Kiosk exposes its own webhook to receive a completion callback
- UI shows a **pending** state, not instant "Checked In"
- Duplicate-scan protection must hold even though confirmations can now arrive **out of order**

Full breakdown of what was dropped, modified, and added is in
[`SCOPE_DELTA_ANALYSIS.md`](./SCOPE_DELTA_ANALYSIS.md).

### Files (overwrite Day 3's versions of the same files, in place)

- `printer_vendor/app.py` — `POST /queue/print` returns `202`
  immediately; two background worker threads process jobs with
  randomized delay and call back via a signed webhook, which is what
  actually produces out-of-order completions rather than just
  simulating the possibility of it
- `kiosk/app.py` — `POST /checkin` now returns `pending`, not
  `Checked In`; new `POST /webhook/print-complete` verifies an HMAC
  signature (reusing the Day 1-2 technique) before trusting the
  callback; new `GET /status/<attendee_id>` for polling
- `state/checkin_state.py` — extended to a two-phase
  `pending → checked_in` model, with a `job_id`-based idempotency
  guard so a duplicate/out-of-order webhook redelivery is a safe
  no-op instead of corrupting state
- `tests/test_pivot.py` — new test suite for the async behavior

### How to run

```bash
python3 printer_vendor/app.py     # terminal 1, port 8000
python3 kiosk/app.py              # terminal 2, port 8001
python3 tests/test_pivot.py       # terminal 3
```

### Verified behavior

| Case                                                         | Expected                                                                               | Actual                                                     |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Check-in response                                            | `202 pending` in <1s (not a ~1.5s block)                                             | ✅ confirmed (0.01s)                                       |
| Status after webhook confirms                                | `checked_in`                                                                         | ✅ confirmed                                               |
| Duplicate scan while pending                                 | Same`job_id`, no second print queued                                                 | ✅ confirmed                                               |
| Duplicate scan after checked_in                              | `already_checked_in` (unchanged from Day 3)                                          | ✅ confirmed                                               |
| Same webhook delivered twice (simulating out-of-order/retry) | Second delivery is a safe no-op                                                        | ✅ confirmed                                               |
| Unsigned webhook                                             | Rejected,`401`                                                                       | ✅ confirmed                                               |
| Out-of-order completion                                      | An attendee scanned*second* can be confirmed checked-in *before* one scanned first | ✅ observed directly in a live run (2.15s / 0.62s / 0.93s) |

### Notable blockers (see Learning & Blocker Journal for full writeup)

- A stale `kiosk/app.py` process left running on port 8001 from an
  earlier session caused the Day 4 test to fail against Day 3's old
  synchronous behavior, even after the file itself had been correctly
  updated — diagnosed by comparing the response (`200`, ~1.5s) against
  what the new code should return (`202`, <1s).

---

## Non-negotiable rules this repo follows

- Obsolete code from before the pivot is marked deprecated, not deleted or
  left running in parallel.
- Same repo, same commit history, start to finish — no separate repo per day.
- The Adaptability Index (Assignment 3) is intentionally **not**
  included in this public repo, since it's required to stay
  confidential — submitted separately once the sprint's submission
  form is released.
