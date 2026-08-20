"""
kiosk/app.py — Day 4 (post-pivot)

DEPRECATED (Day 3): the synchronous flow that called the vendor's
POST /print and blocked until it returned, then immediately showed
"Checked In". REMOVED here — see git history / the
`feature/day3-solstice-original` branch for that version. Not kept
running in parallel with the code below, per the sprint's
non-negotiable rules.

NEW (Day 4):
  POST /checkin
    - if already checked_in -> return that immediately (unchanged
      behavior from Day 3)
    - if already pending -> return pending, do NOT queue a second
      print job for the same attendee
    - otherwise -> publish a job to the vendor's queue, mark this
      attendee "pending", and return immediately. The UI can no
      longer show "Checked In" here — only "pending".

  POST /webhook/print-complete
    - NEW. Receives the vendor's async completion callback.
    - Verifies the HMAC signature (same technique as the Day 1-2
      solo prototype) before trusting the payload.
    - Uses complete_job(), which is idempotent by job_id, so a
      duplicate or out-of-order webhook redelivery is handled safely
      instead of corrupting state.

  GET /status/<attendee_id>
    - NEW. Lets the UI poll for pending -> checked_in instead of
      getting an instant answer.

Run: python3 kiosk/app.py   (port 8001)
"""

import hashlib
import hmac
import sys
import os

import requests
from flask import Flask, request, jsonify

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from state.checkin_state import get_status, start_pending, complete_job

app = Flask(__name__)

PRINTER_VENDOR_QUEUE_URL = "http://127.0.0.1:8000/queue/print"
WEBHOOK_SECRET = b"solstice-shared-secret-change-me"  # must match printer_vendor/app.py


def verify_signature(raw_body, signature_header):
    if not signature_header:
        return False
    expected = hmac.new(WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()
    # constant-time comparison — same practice as the Day 1-2 prototype
    return hmac.compare_digest(expected, signature_header)


@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json(force=True)
    attendee_id = data.get("attendee_id")
    name = data.get("name")

    if not attendee_id or not name:
        return jsonify({"status": "error", "reason": "missing attendee_id or name"}), 400

    current = get_status(attendee_id)

    # --- Duplicate-scan protection, now with two states to check ---
    if current is not None:
        if current["status"] == "checked_in":
            return jsonify({
                "status": "already_checked_in",
                "message": f"{name} was already checked in.",
                "job_id": current["job_id"],
            }), 200
        if current["status"] == "pending":
            return jsonify({
                "status": "pending",
                "message": f"{name}'s badge is already being printed — please wait.",
                "job_id": current["job_id"],
            }), 200

    # --- Publish to the vendor's queue instead of calling it synchronously ---
    try:
        resp = requests.post(
            PRINTER_VENDOR_QUEUE_URL,
            json={"attendee_id": attendee_id, "name": name},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "reason": f"printer vendor unreachable: {e}"}), 502

    if resp.status_code != 202 or resp.json().get("status") != "queued":
        return jsonify({"status": "error", "reason": "failed to queue print job"}), 502

    job_id = resp.json()["job_id"]
    start_pending(attendee_id, job_id)

    # The UI shows a pending state here — NOT "Checked In". That only
    # happens once the webhook below actually confirms the print.
    return jsonify({
        "status": "pending",
        "attendee_id": attendee_id,
        "name": name,
        "job_id": job_id,
    }), 202


@app.route("/webhook/print-complete", methods=["POST"])
def webhook_print_complete():
    raw_body = request.get_data()
    signature = request.headers.get("X-Signature")

    if not verify_signature(raw_body, signature):
        return jsonify({"status": "error", "reason": "invalid or missing signature"}), 401

    data = request.get_json(force=True)
    job_id = data.get("job_id")

    if not job_id:
        return jsonify({"status": "error", "reason": "missing job_id"}), 400

    changed = complete_job(job_id)
    if not changed:
        # Either an unknown job_id, or (more likely in practice) a
        # duplicate/out-of-order redelivery of a job already marked
        # checked_in. Either way, respond 200 — this is not an error
        # from the vendor's point of view, just a no-op on our side.
        return jsonify({"status": "already_processed", "job_id": job_id}), 200

    return jsonify({"status": "ok", "job_id": job_id}), 200


@app.route("/status/<attendee_id>", methods=["GET"])
def status(attendee_id):
    current = get_status(attendee_id)
    if current is None:
        return jsonify({"status": "not_found"}), 404
    return jsonify(current), 200


if __name__ == "__main__":
    app.run(port=8001, debug=False)