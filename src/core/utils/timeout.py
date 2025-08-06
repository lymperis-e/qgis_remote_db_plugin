# timeout.py

import sys
import time
import threading
import signal
from contextlib import contextmanager
from types import FrameType
from typing import Optional

__all__ = ["timeout"]

# ---------------------------
# Unix implementation (thread-safe)
# ---------------------------


@contextmanager
def _unix_timeout(seconds: int):
    if threading.current_thread() is not threading.main_thread():
        # signal.signal can only be used in the main thread
        raise RuntimeError("signal-based timeout only works in the main thread")

    def _handler(signum: int, frame: Optional[FrameType]):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


# ---------------------------
# Windows implementation (threading-based)
# ---------------------------


@contextmanager
def _thread_timeout(seconds: int):
    expired = threading.Event()

    def timer_func():
        time.sleep(seconds)
        expired.set()

    timer_thread = threading.Thread(target=timer_func, daemon=True)
    timer_thread.start()

    try:
        yield_checker = _YieldChecker(expired, seconds)
        yield yield_checker
        if expired.is_set():
            raise TimeoutError(f"Operation timed out after {seconds} seconds")
    finally:
        expired.set()  # In case of early exit


class _YieldChecker:
    """
    Optional: Expose this to allow checking timeout inside a loop.
    E.g.:
        with timeout(5) as t:
            while not t.timed_out:
                ...
    """

    def __init__(self, expired_event: threading.Event, timeout_seconds: int):
        self._expired = expired_event
        self._timeout = timeout_seconds

    @property
    def timed_out(self):
        return self._expired.is_set()

    @property
    def timeout(self):
        return self._timeout


# ---------------------------
# Cross-platform selector
# ---------------------------


def timeout(seconds: int):
    """
    Cross-platform, thread-safe timeout context manager.

    Usage:
        with timeout(5):
            long_running_task()

    Raises:
        TimeoutError if the block exceeds the specified timeout.
    """
    if (
        sys.platform.startswith("win")
        or threading.current_thread() is not threading.main_thread()
    ):
        return _thread_timeout(seconds)

    return _unix_timeout(seconds)
