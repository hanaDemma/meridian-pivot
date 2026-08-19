# Learning & Blocker Journal — Webhook Verification

**Date:** 19 August 2026
**Time zone:** EAT (UTC+03:00)
**Note:** Times below are approximate session times.

## 1. Learning Objective

I set out to build and verify a Flask webhook endpoint that accepts genuine stock-update events and rejects altered or unsigned requests. The key learning goal was to understand the full verification path: sign the exact request bytes with HMAC-SHA256, safely compare the supplied signature, and only then trust and validate the JSON payload.

## 2. What I Learned

- HMAC needs byte values: the secret string must be encoded, and the webhook body must stay as raw bytes while the signature is calculated.
- The HMAC object’s `hexdigest()` method produces a transport-friendly hexadecimal string for the `X-Signature` header.
- `hmac.compare_digest()` is safer than `==` for a signature comparison because it avoids content-dependent early exits. It also expects compatible types, such as two strings.
- In Flask, `request.get_data()` provides the raw request bytes needed for verification. JSON should be parsed only after the signature passes, because parsing and re-serializing can change the exact byte sequence that was signed.
- A failed test does not always mean the new code is wrong. Confirming the running process and port ownership was necessary to distinguish a stale server from a signature defect.

## 3. Real-Time Log

### 09:30 EAT (approx.) — Missing-signature type error

**What I tried:** I called the unguarded verification function with a valid body but `None` for the received signature:

```python
verify_signature("my-secret", b'{"product_id":"SKU-001"}', None)
```

**Observed result:**

```text
Traceback (most recent call last):
  File "<stdin>", line 14, in <module>
  File "<stdin>", line 11, in verify_signature
TypeError: unsupported operand types(s) or combination of types: 'str' and 'NoneType'
```

**Investigation:** I checked the values passed to `compare_digest()`. The computed signature was a hexadecimal `str`, while a missing HTTP header became `None`.

**Root cause:** `hmac.compare_digest()` accepts two compatible values—both strings or both bytes-like objects. It cannot compare a `str` to `NoneType`.

**Fix:** I added an early guard before comparison:

```python
if not received_signature:
    return False
```

This turns a missing signature into a clean verification failure instead of a server exception.

### 09:40 EAT (approx.) — Unexpected 401 caused by a stale receiver

**What I tried:** I started the receiver and sent a separately generated, valid signed request using Python `requests`.

**Observed result:**

```text
status: 401
body: {"error":"invalid signature"}
```

**Investigation:** I added a temporary `print("HIT NEW CODE")` marker to the route and checked the port listener. Port 5000 was already owned by PID `32752`, running `Receiver.py`.

**Root cause:** The request was reaching an older receiver process rather than the version of the code I had just saved. The 401 was therefore a false signal, not evidence that the new HMAC logic was invalid.

**Fix:** I stopped the confirmed port-5000 process, restarted the current receiver, reran the signed request, and removed the temporary marker after the test.

## 4. Blockers and Follow-Up Work

| Item                         | Why it matters                                               | Next step                                                                       |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| Replay protection            | A valid signed request could be captured and resent.         | Sign a timestamp and event ID; reject stale timestamps and duplicate event IDs. |
| Secret management            | A hardcoded development secret is not safe for deployment.   | Read`WEBHOOK_SECRET` from deployment configuration or a secrets manager.      |
| Durable storage              | The in-memory stock cache is lost on restart.                | Store inventory state in Redis or a database.                                   |
| Input constraints            | Field presence alone does not guarantee valid values.        | Validate data types and allowed formats for product IDs and quantities.         |
| Rate limiting and audit logs | The endpoint needs operational protections and traceability. | Apply rate limits and add structured event logs.                                |

## 5. Final State

### 09:48 EAT (approx.) — End-to-end verification passed

After restarting the current receiver, the independently generated valid request returned:

```text
status: 200
body: {"product_id":"SKU-001","status":"received"}
```

The stock query after the valid webhook confirmed the stored value remained correct:

```text
GET /stock/SKU-001 -> {"product_id":"SKU-001","quantity":42}
```

The earlier tampered request attempted to change the quantity to `99999`, but it was rejected with `401`; the verified value therefore remained `42`.

## 6. Reflection

This exercise made the verification order clear to me: preserve and sign the raw bytes, verify the signature safely, then parse and validate the data. I also learned that good debugging means testing the execution environment, not only reading the code. The stale-process incident looked exactly like a cryptographic failure at first, but checking the active listener showed that the test was reaching the wrong server. I now have evidence that the local proof of concept handles a valid signed event, refuses tampered or unsigned input, and fails safely when the signature header is absent. Production use would still require replay protection, managed secrets, durable storage, and operational safeguards.
