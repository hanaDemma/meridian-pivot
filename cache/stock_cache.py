"""
cache/stock_cache.py

Thread-safe in-memory cache of warehouse stock levels.

Both the poller (writer) and the query API (reader) import this
module, so they must share the same process for the in-memory dict
to work (see api/app.py, which runs the poller in a background
thread rather than as a separate process, for exactly this reason).
"""

import threading
import time

_lock = threading.Lock()
_cache = {}
_last_updated = None


def update_stock(stock_dict):
    """Called by the poller after each successful warehouse fetch."""
    global _last_updated
    with _lock:
        _cache.clear()
        _cache.update(stock_dict)
        _last_updated = time.time()


def get_stock(sku):
    with _lock:
        return _cache.get(sku)


def get_all_stock():
    with _lock:
        return dict(_cache)


def last_updated():
    with _lock:
        return _last_updated