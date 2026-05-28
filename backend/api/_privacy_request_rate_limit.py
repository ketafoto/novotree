"""
Per-IP rate limiter for the public POST /privacy/request endpoint.

The global limiter in backend/main.py is 60s-windowed and tuned for normal
traffic. Privacy-request submissions need a much narrower window
(5 per hour per IP) to bound abuse of a public, unauthenticated endpoint
without blocking legitimate retries.

In-memory state — process-local, resets on restart. Acceptable because the
endpoint itself is low-volume and abuse beyond restart cadence is bounded
by the global limiter too. If we ever need durable per-IP counters
(e.g. behind multiple backend instances), promote this to Redis.
"""

import time
from collections import defaultdict, deque

# Per-IP submission timestamps. Bounded by the trim in _trim_window().
_windows: dict[str, deque[float]] = defaultdict(deque)

_LIMIT = 5
_WINDOW_SECONDS = 3600


def _trim_window(window: deque[float], now: float) -> None:
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()


def check_privacy_request_rate(client_ip: str) -> bool:
    """
    Return True if the request is within the per-IP quota and record it.
    Return False if the IP has exceeded 5 submissions in the last hour.
    """
    now = time.time()
    window = _windows[client_ip]
    _trim_window(window, now)
    if len(window) >= _LIMIT:
        return False
    window.append(now)
    return True


def reset_for_tests() -> None:
    _windows.clear()
