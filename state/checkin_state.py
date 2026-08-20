"""
state/checkin_state.py — Day 4 (post-pivot)

Extends Day 3's simple "checked in or not" state into a two-phase
model required by the async pivot:

  pending      -> print job queued, waiting on the vendor's webhook
  checked_in   -> webhook confirmed the print actually succeeded

Two lookups are needed because the webhook confirms by job_id, but
scans/duplicate-checks happen by attendee_id:
  _state          : attendee_id -> {"status": ..., "job_id": ...}
  _job_to_attendee: job_id -> attendee_id
  _completed_jobs : set of job_ids already finalized

_completed_jobs is what makes webhook handling IDEMPOTENT — the spec
explicitly says confirmations "may now arrive out of order" (and, by
extension, a webhook could be retried/duplicated by the vendor, which
is normal for real message-queue systems). Without this guard, a
duplicate webhook delivery could reprocess state harmlessly here, but
in a real system could double-charge, double-notify, etc. Guarding by
job_id is the correct fix, not guarding by attendee_id.
"""

import threading

_lock = threading.Lock()
_state = {}             # attendee_id -> {"status": "pending"|"checked_in", "job_id": str}
_job_to_attendee = {}   # job_id -> attendee_id
_completed_jobs = set()  # job_ids already finalized (idempotency guard)


def get_status(attendee_id):
    with _lock:
        return _state.get(attendee_id)


def start_pending(attendee_id, job_id):
    """Called when a print job is queued. Does NOT mean checked in yet."""
    with _lock:
        _state[attendee_id] = {"status": "pending", "job_id": job_id}
        _job_to_attendee[job_id] = attendee_id


def complete_job(job_id):
    """
    Called by the webhook handler when the vendor confirms a print job
    finished. Returns True if this call actually changed state (first
    time seeing this job_id), False if it was a no-op (unknown job, or
    a duplicate/out-of-order redelivery of a job already completed).
    """
    with _lock:
        if job_id in _completed_jobs:
            return False  # duplicate delivery — already processed, ignore safely

        attendee_id = _job_to_attendee.get(job_id)
        if attendee_id is None:
            return False  # unknown job_id — nothing to complete

        _completed_jobs.add(job_id)
        _state[attendee_id] = {"status": "checked_in", "job_id": job_id}
        return True


def all_state():
    with _lock:
        return dict(_state)