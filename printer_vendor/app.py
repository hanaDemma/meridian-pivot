"""
printer_vendor/app.py — Day 4 (post-pivot)

DEPRECATED (Day 3): the synchronous POST /print endpoint that blocked
until printing finished. It is REMOVED here, not left running
alongside the new endpoint — see git history (Day 3 commits / the
`feature/day3-solstice-original` branch) for that version.

NEW (Day 4): the vendor now works like a real message-queue-backed
system:
  1. POST /queue/print accepts a job and returns 202 immediately —
     the caller does NOT wait for printing to finish.
  2. A background worker "processes the queue" (simulated delay),
     then calls back to the kiosk's webhook endpoint once the print
     job actually completes.
  3. Multiple jobs are processed by several worker threads with
     randomized delay, so completions can genuinely arrive
     out of order — exactly the condition the spec calls out.

The callback is HMAC-signed (same technique from the Day 1-2 solo
prototype) so the kiosk can verify the completion notice really came
from this vendor and wasn't spoofed.

Run: python3 printer_vendor/app.py   (port 8000)
"""

import hashlib
import hmac
import json
import queue
import random
import threading
import time
import uuid

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

KIOSK_WEBHOOK_URL = "http://127.0.0.1:8001/webhook/print-complete"
WEBHOOK_SECRET = b"solstice-shared-secret-change-me"  # shared secret, same on both sides

_job_queue = queue.Queue()


def sign(payload_bytes):
    return hmac.new(WEBHOOK_SECRET, payload_bytes, hashlib.sha256).hexdigest()


def worker_loop(worker_name):
    while True:
        job = _job_queue.get()
        # Randomized delay simulates real printer hardware + queue
        # latency, and is what causes jobs to complete OUT OF ORDER
        # relative to the order they were submitted.
        delay = random.uniform(1.0, 3.0)
        print(f"[vendor:{worker_name}] printing job {job['job_id']} for {job['name']} (~{delay:.1f}s)...")
        time.sleep(delay)

        body = {
            "job_id": job["job_id"],
            "attendee_id": job["attendee_id"],
            "status": "success",
        }
        raw = json.dumps(body).encode("utf-8")
        signature = sign(raw)

        try:
            requests.post(
                KIOSK_WEBHOOK_URL,
                data=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": signature,
                },
                timeout=10,
            )
            print(f"[vendor:{worker_name}] webhook sent for job {job['job_id']}")
        except requests.exceptions.RequestException as e:
            print(f"[vendor:{worker_name}] webhook delivery failed: {e}")

        _job_queue.task_done()


# Two workers running concurrently is what actually produces
# out-of-order completions (a job submitted second can finish first).
for i in range(2):
    threading.Thread(target=worker_loop, args=(f"worker{i+1}",), daemon=True).start()


@app.route("/queue/print", methods=["POST"])
def queue_print():
    data = request.get_json(force=True)
    attendee_id = data.get("attendee_id")
    name = data.get("name")

    if not attendee_id or not name:
        return jsonify({"status": "error", "reason": "missing attendee_id or name"}), 400

    job_id = str(uuid.uuid4())
    _job_queue.put({"job_id": job_id, "attendee_id": attendee_id, "name": name})
    print(f"[vendor] queued job {job_id} for {name} ({attendee_id})")

    # Returns immediately — this is the whole point of the pivot.
    return jsonify({"status": "queued", "job_id": job_id}), 202


if __name__ == "__main__":
    app.run(port=8000, debug=False)