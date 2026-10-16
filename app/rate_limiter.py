import time
import threading
from typing import Dict, Tuple

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate # tokens added per second
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def allow_request(self, tokens_required: int = 1) -> Tuple[bool, int]:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.last_refill = now

            # Add newly generated tokens
            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.refill_rate)

            if self.tokens >= tokens_required:
                self.tokens -= tokens_required
                return True, int(self.tokens)
            else:
                return False, 0


class RateLimiter:
    """
    Per-client IP token bucket rate limiter.
    """
    def __init__(self, default_capacity: int = 100, default_refill_rate: float = 10.0):
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.buckets: Dict[str, TokenBucket] = {}
        self._map_lock = threading.Lock()

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        with self._map_lock:
            if client_id not in self.buckets:
                self.buckets[client_id] = TokenBucket(self.default_capacity, self.default_refill_rate)
            bucket = self.buckets[client_id]

        return bucket.allow_request()
