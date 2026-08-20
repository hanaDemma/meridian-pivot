"""
printer_vendor/app.py

Stands in for Solstice's badge-printer vendor's SYNCHRONOUS print API —
the one being deprecated on Day 4 (that's when it gets replaced by a
message queue + webhook callback instead).

Contract (Day 3 original spec):
  POST /print
  body: {"attendee_id": "...", "name": "..."}
  -> blocks for a moment (simulating real printer hardware), then returns
     200 {"status": "success", "job_id": "..."} once printing is done.

Run: python3 printer_vendor/app.py   (port 8000)
"""

import time
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

PRINT_DELAY_SECONDS = 1.5  # simulated printer hardware latency


@app.route("/print", methods=["POST"])
def print_badge():
    data = request.get_json(force=True)
    attendee_id = data.get("attendee_id")
    name = data.get("name")

    if not attendee_id or not name:
        return jsonify({"status": "error", "reason": "missing attendee_id or name"}), 400

    print(f"[vendor] Printer received job for {name} ({attendee_id}) — printing...")
    time.sleep(PRINT_DELAY_SECONDS)  # the blocking call the kiosk waits on

    job_id = str(uuid.uuid4())
    print(f"[vendor] Print job {job_id} complete for {attendee_id}")

    return jsonify({"status": "success", "job_id": job_id}), 200


if __name__ == "__main__":
    app.run(port=8000, debug=False)