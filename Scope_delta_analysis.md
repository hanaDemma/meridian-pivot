
# Scope Delta Analysis

**Project:** Solstice Events Co. — Event Check-In Kiosk
**Sprint:** The Meridian Pivot
**Author:** Solo submission

---

## 1. Original Spec (Day 3)

Client requirement, as given:

- Staff scan an attendee's QR code → app calls the badge-printer vendor's REST API **synchronously**.
- App waits for the print job's success response before doing anything else.
- "Checked In" is shown on screen only once printing has actually succeeded.
- Must correctly handle ≥3 test attendees, including one duplicate-scan case — an attendee already checked in must not get a second badge printed.

**State at end of Day 3:** fully implemented, tested, and passing (`kiosk/app.py`, `printer_vendor/app.py`, `state/checkin_state.py`, `tests/test_checkin.py`). Every check-in blocked for ~1.5s waiting on the printer, then returned `"Checked In"`. Duplicate scans were rejected instantly by checking an in-memory `attendee_id → job_id` map.

---

## 2. The Pivot (Day 4)

Client announcement, non-negotiable, no deadline extension:

> Solstice's badge-printer vendor is deprecating the synchronous print API. The kiosk service must be rebuilt around an asynchronous model: publish a print request onto the vendor's message queue, and expose a webhook endpoint to receive a callback once the print job actually completes. The UI can no longer show "Checked In" instantly — it must reflect a pending state until the webhook confirmation arrives. Duplicate-scan protection still has to hold, even though confirmations may now arrive out of order.

---

## 3. Dropped

| Item                                                         | Why                                                                                                                        |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `POST /print` synchronous endpoint (`printer_vendor`)    | Deprecated by the vendor. The kiosk can no longer make a blocking call and wait for an immediate response.                 |
| Blocking`requests.post(...)` call inside `kiosk/checkin` | Replaced entirely — the kiosk must return before the print job is even attempted, not after.                              |
| Immediate`"Checked In"` response                           | No longer valid under the spec. Printing success is no longer knowable at the moment the endpoint returns.                 |
| Single-state`checked_in: true/false` model                 | Replaced — a boolean can't represent "print requested but not yet confirmed," which the new spec requires the UI to show. |

None of this code was deleted outright — it remains visible in git history (see the `feature/day3-solstice-original` branch and Day 3 commits) rather than left running alongside the new version, per the sprint's non-negotiable rule against parallel old/new code.

## 4. Added

| Item                                                               | Purpose                                                                                                                                                                                                |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `POST /queue/print` (`printer_vendor`)                         | Accepts a print job and returns`202 Accepted` immediately; does not block the caller.                                                                                                                |
| Background worker threads (`printer_vendor`)                     | Simulate the vendor's own queue processing. Two workers run concurrently with randomized delay specifically to produce genuinely out-of-order completions, not just simulate the*possibility* of it. |
| `POST /webhook/print-complete` (`kiosk`)                       | New endpoint the vendor calls back on. Verifies an HMAC-SHA256 signature before trusting the payload — reusing the signature-verification technique built in Assignment 1's solo prototype.           |
| `GET /status/<attendee_id>` (`kiosk`)                          | Lets the UI (or a test) poll for the pending → checked_in transition, since the response can no longer be known synchronously.                                                                        |
| `pending` state (`state/checkin_state.py`)                     | New status between "not scanned" and "checked in," tracked alongside the`job_id` that will eventually confirm it.                                                                                    |
| `job_id → attendee_id` reverse map (`state/checkin_state.py`) | Needed because the webhook confirms completion by`job_id`, not `attendee_id` — the state layer has to be able to resolve one from the other.                                                      |
| `_completed_jobs` idempotency set (`state/checkin_state.py`)   | Directly addresses "confirmations may arrive out of order" — guards against the same job being processed twice if the vendor's webhook is retried or redelivered.                                     |

## 5. Modified

| Item                                       | Before (Day 3)                                        | After (Day 4)                                                                                                                  |
| ------------------------------------------ | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `POST /checkin` response                 | Blocks ~1.5s, returns`200 "Checked In"`             | Returns almost immediately,`202 "pending"`                                                                                   |
| Duplicate-scan check                       | Checks only`checked_in`                             | Now checks both`pending` (don't re-queue) and `checked_in` (don't reprint) — two distinct duplicate cases instead of one  |
| What "duplicate protection" guards against | A second synchronous print call for the same attendee | That, plus: a second webhook delivery for the same completed job, and a second queue submission while a job is still in flight |

---

## 6. Regression Check

Re-ran `tests/test_checkin.py` (Day 3 test) against the Day 3 code on its own branch (`feature/day3-solstice-original`) — still passes independently, confirming the "before" state is intact and unmodified in history.

Ran `tests/test_pivot.py` (Day 4 test) against the current `kiosk/app.py` / `printer_vendor/app.py` — confirms:

- Check-in returns `pending` in <1s (not blocking ~1.5s like Day 3)
- Status correctly transitions to `checked_in` once the webhook fires
- A duplicate scan while pending returns the *same* `job_id` rather than queuing a second job
- A duplicate scan after completion still correctly returns `already_checked_in`
- A manually replayed webhook for an already-completed `job_id` is a safe no-op (`already_processed`), proving the idempotency guard works under redelivery
- An unsigned webhook is rejected with `401`, proving the endpoint doesn't blindly trust any POST to it

No old feature was silently broken by the pivot — every Day 3 guarantee (checked-in state persists, duplicates rejected) still holds, just re-implemented for an async world.

---

## 7. Trade-offs and Open Backlog

**Chosen approach:** simulate the message queue with an in-process Python `queue.Queue` and worker threads inside the vendor mock, rather than standing up a real broker (RabbitMQ, SQS, etc.).

- **Pro:** no external infrastructure dependency, fast to build and test under the 48-hour constraint, and still genuinely demonstrates the async request/response-decoupling the spec asks for.
- **Con:** not representative of a real production message queue — no persistence (a queued job is lost if the vendor process crashes), no delivery guarantees, no dead-letter handling for a job that fails to print.

**Reprioritized backlog, if this were a real production pivot:**

1. Replace the in-process queue with a real broker (Redis Streams or RabbitMQ) so jobs survive a process restart.
2. Add a retry/backoff policy for failed webhook deliveries from the vendor side (currently a failed `requests.post` in the worker is just logged and dropped).
3. Add a timeout path in the kiosk: if a job stays `pending` too long, surface that to staff instead of silently waiting forever.
4. Persist state (`state/checkin_state.py`) to a real store instead of an in-memory dict, so a kiosk restart doesn't lose in-flight check-ins.
5. Add signature verification on the `/queue/print` request too, not just the webhook callback — currently only the vendor→kiosk direction is authenticated.

Items 1-3 were deprioritized in favor of correctness of the core async flow and duplicate-protection logic, given the non-negotiable deadline. Item 4 was deprioritized since a persistent store adds a real dependency (a database) that wasn't necessary to prove the pivot's core requirement. Item 5 was noted but not built, since the kiosk is the only legitimate caller of that endpoint in this scenario — lower risk than the webhook direction, which needed to accept traffic from an external vendor.
