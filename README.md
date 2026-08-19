
# meridian-pivot — Solo Mini-Prototype: Webhook Verification

## What this is

A minimal proof that a webhook receiver can tell a **genuine** stock-update
push (from "Northstar Retail Co.") apart from a **spoofed or tampered** one,
using HMAC-SHA256 signature verification.

Built for **Assignment 1: Independent Learning & Blocker Log** — the tool
(webhook signature verification) was unfamiliar going in, and the
`LEARNING_BLOCKER_JOURNAL.md` in this repo documents the actual real-time
troubleshooting, including a type-mismatch bug and a false failure caused
by a stale server process.

## Why this tool

It matters for the Meridian Pivot because Day 4's pivot moves the whole
project from *polling* a warehouse API to *receiving* pushed webhook
events. At that point, anyone who finds the endpoint URL could POST fake
stock data unless the receiver checks *who* actually sent it — that's what
this prototype verifies.

## Files

- `Receiver.py` — Flask webhook endpoint with HMAC-SHA256 signature
  verification, plus a `GET /stock/<product_id>` query endpoint
- `Sender.py` — test harness that sends a valid signed request, a
  tampered request, and a request with no signature, to prove the
  verification logic actually rejects bad input rather than just
  accepting everything
- `LEARNING_BLOCKER_JOURNAL.md` — real-time log of the build process,
  including a `TypeError` hit during signature verification and a
  stale-process debugging session
- `logs/` — raw terminal output captured during testing

## How to run

```bash
pip install flask requests

# terminal 1
python Receiver.py

# terminal 2
python Sender.py
```

Both files use the shared secret `"my-secret"` — this must match between
`Receiver.py` and `Sender.py` or every request will fail with `401`
regardless of whether the payload is valid (this happened during
development; see the journal for the full story).

## Verified behavior

| Case                                    | Expected                                  | Actual       |
| --------------------------------------- | ----------------------------------------- | ------------ |
| Valid signed request                    | `200`, stock updated                    | ✅`200`    |
| Tampered payload with stale signature   | `401`, rejected                         | ✅`401`    |
| No signature header                     | `401`, rejected                         | ✅`401`    |
| `GET /stock/SKU-001` after valid push | Returns`42`, not the tampered `99999` | ✅ confirmed |

## Known limitations / what I'd add with more time

- No replay protection — a captured valid request could be resent as-is;
  fix would be signing a timestamp + event ID and rejecting stale/duplicate
  ones
- Hardcoded development secret — should come from an environment variable
  or secrets manager outside local testing
- In-memory stock cache — lost on restart; would use Redis or a database
- No rate limiting on the webhook endpoint
- Minimal input validation — checks field presence but not value types/formats

See `LEARNING_BLOCKER_JOURNAL.md` for the full build and debugging history.
