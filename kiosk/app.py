"""
kiosk/app.py — Day 3 / Original Spec

Solstice Events Co. event check-in kiosk.

Spec:
  - Staff scan an attendee's QR code -> app calls the badge-printer
    vendor's REST API SYNCHRONOUSLY.
  - App waits for the print job's success response before doing
    anything else.
  - "Checked In" is shown on screen only once printing has actually
    succeeded.
  - Must correctly handle >= 3 test attendees, including one
    duplicate-scan case: an attendee already checked in must NOT get
    a second badge printed.

This is the "before" version — Day 4 kills this synchronous model and
rebuilds around a message queue + webhook callback instead. Keep this
file intact after the pivot; mark it deprecated rather than deleting it.

Run: python3 kiosk/app.py   (port 8001)
"""

import sys
import os
import requests
from flask import Flask, request, jsonify

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from state.checkin_state import is_checked_in, mark_checked_in, get_job_id

app = Flask(__name__)

PRINTER_VENDOR_URL = "http://127.0.0.1:8000/print"


@app.route("/checkin", methods=["POST"])
def checkin():
    data = request.get_json(force=True)
    attendee_id = data.get("attendee_id")
    name = data.get("name")

    if not attendee_id or not name:
        return jsonify({"status": "error", "reason": "missing attendee_id or name"}), 400

    # --- Duplicate-scan protection ---
    if is_checked_in(attendee_id):
        return jsonify({
            "status": "already_checked_in",
            "message": f"{name} was already checked in.",
            "job_id": get_job_id(attendee_id),
        }), 200

    # --- Synchronous call to the vendor's print API ---
    # The kiosk BLOCKS here until the vendor responds. Nothing is shown
    # to staff until this call returns.
    try:
        resp = requests.post(
            PRINTER_VENDOR_URL,
            json={"attendee_id": attendee_id, "name": name},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "reason": f"printer vendor unreachable: {e}"}), 502

    if resp.status_code != 200 or resp.json().get("status") != "success":
        return jsonify({"status": "error", "reason": "print job failed"}), 502

    job_id = resp.json()["job_id"]
    mark_checked_in(attendee_id, job_id)

    # Only NOW, after the print has actually succeeded, do we show "Checked In"
    return jsonify({
        "status": "Checked In",
        "attendee_id": attendee_id,
        "name": name,
        "job_id": job_id,
    }), 200


if __name__ == "__main__":
    app.run(port=8001, debug=False)