import threading
import time
from collections import defaultdict


class RateLimiter:
    """Fixed one-minute window counter. Process-local, which matches the single API worker."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        now = time.time()
        with self._lock:
            recent = [stamp for stamp in self._hits[key] if now - stamp < 60]
            if len(recent) >= max(1, limit):
                self._hits[key] = recent
                return False
            recent.append(now)
            self._hits[key] = recent
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()
