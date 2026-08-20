

import threading

_lock = threading.Lock()
_checked_in = {}  # attendee_id -> job_id


def is_checked_in(attendee_id):
    with _lock:
        return attendee_id in _checked_in


def mark_checked_in(attendee_id, job_id):
    with _lock:
        _checked_in[attendee_id] = job_id


def get_job_id(attendee_id):
    with _lock:
        return _checked_in.get(attendee_id)


def all_checked_in():
    with _lock:
        return dict(_checked_in)