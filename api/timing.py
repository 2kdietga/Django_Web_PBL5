import logging
import time

logger = logging.getLogger(__name__)


class StepTimer:
    def __init__(self, name="timer", enabled=True):
        self.name = name
        self.enabled = enabled
        self.start = time.perf_counter()
        self.last = self.start
        self.data = {}

    def mark(self, step_name):
        if not self.enabled:
            return

        now = time.perf_counter()

        step_ms = round((now - self.last) * 1000, 2)
        total_ms = round((now - self.start) * 1000, 2)

        self.data[step_name] = step_ms
        self.data[f"{step_name}_total"] = total_ms

        self.last = now

    def total_ms(self):
        return round((time.perf_counter() - self.start) * 1000, 2)

    def as_dict(self):
        if not self.enabled:
            return {}

        return {
            "_timing_ms": self.data,
            "_total_ms": self.total_ms(),
        }

    def log(self):
        if not self.enabled:
            return

        logger.warning(
            "[%s] total=%sms timing_ms=%s",
            self.name,
            self.total_ms(),
            self.data,
        )