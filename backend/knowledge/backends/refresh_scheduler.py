# backend/knowledge/backends/refresh_scheduler.py
from __future__ import annotations

import threading
import time
from typing import Callable


class RefreshScheduler:
    """Background scheduler for periodic knowledge refresh tasks.

    Supports independent schedules for different refresh targets:
    RSS, GitHub, Projects, News, Knowledge Graph, etc.
    """

    def __init__(self):
        self._jobs: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def schedule(self, name: str, interval_seconds: int, callback: Callable[[], None]) -> None:
        """Schedule a recurring refresh job.

        Args:
            name: Unique job name.
            interval_seconds: Interval between refreshes.
            callback: Async or sync callback to execute.
        """
        self.cancel(name)

        def _run():
            try:
                callback()
            except Exception:
                pass
            finally:
                self._reschedule(name, interval_seconds, callback)

        with self._lock:
            timer = threading.Timer(interval_seconds, _run)
            timer.daemon = True
            self._jobs[name] = timer
            timer.start()

    def _reschedule(self, name: str, interval_seconds: int, callback: Callable[[], None]) -> None:
        with self._lock:
            if name in self._jobs:
                timer = threading.Timer(interval_seconds, self._run_job, args=(name, interval_seconds, callback))
                timer.daemon = True
                self._jobs[name] = timer
                timer.start()

    def _run_job(self, name: str, interval_seconds: int, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            pass
        finally:
            self._reschedule(name, interval_seconds, callback)

    def cancel(self, name: str) -> None:
        """Cancel a scheduled refresh job."""
        with self._lock:
            timer = self._jobs.pop(name, None)
            if timer:
                timer.cancel()

    def cancel_all(self) -> None:
        """Cancel all scheduled refresh jobs."""
        with self._lock:
            for timer in self._jobs.values():
                timer.cancel()
            self._jobs.clear()
