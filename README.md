# meridian-pivot



# Solo Mini-Prototype — Webhook Verification

## What this is

A minimal proof that a webhook receiver can tell a **genuine** stock-update
push (from "Northstar Retail Co.") apart from a **spoofed or tampered** one,
using HMAC-SHA256 signature verification.

## Why this tool

Assigned/chosen because I'd never implemented webhook signature verification
before. It matters for the Meridian Pivot because Day 4's pivot moves the
whole project from *polling* a warehouse API to *receiving* pushed webhook
events — at that point, anyone who finds the endpoint URL could POST fake
stock data unless the receiver checks *who* actually sent it.

## Files

- `receiver.py` — Flask webhook endpoint with signature verification +
  a `/stock/<product_id>` query endpoint
- `sender.py` — test harness that sends a valid request, a tampered request,
  and a request with no signature, to prove the check actually works
- `receiver.log` — output from the live run used to verify this prototype

## How to run

```bash
pip install flask requests
python3 receiver.py            # terminal 1
python3 sender.py              # terminal 2
```

## Verified behavior (see receiver.log / journal for full run)

| Case                                | Expected                                     | Actual       |
| ----------------------------------- | -------------------------------------------- | ------------ |
| Valid signature                     | 200, stock updated                           | ✅ 200       |
| Tampered payload w/ stale signature | 401, rejected                                | ✅ 401       |
| No signature header                 | 401, rejected                                | ✅ 401       |
| Query endpoint after valid push     | Returns correct stored value (42, not 99999) | ✅ confirmed |

## What I'd add with more time

- Timestamp + nonce in the signed payload, to prevent replay attacks
  (a valid signed request could currently be resent as-is)
- Real persistence (Redis/DB) instead of the in-memory dict
- Rate limiting on the endpoint
