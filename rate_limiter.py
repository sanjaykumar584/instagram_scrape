import time
import threading
from typing import Optional
from logger_config import get_logger

logger = get_logger("rate_limit")

class RateLimitTracker:
    """Track rate limits and implement circuit breaker pattern"""
    
    def __init__(self):
        self.blocked_until = 0.0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self._lock = threading.RLock()
        self.max_failures_before_block = int(__import__('os').getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
    
    def is_blocked(self) -> bool:
        """Check if requests are blocked due to rate limiting"""
        with self._lock:
            return time.time() < self.blocked_until
    
    def get_wait_time(self) -> float:
        """Get remaining wait time if blocked"""
        with self._lock:
            if self.blocked_until > time.time():
                return self.blocked_until - time.time()
            return 0.0
    
    def record_rate_limit(self, retry_after: Optional[int] = None) -> float:
        """Record rate limit hit and return wait time"""
        with self._lock:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # Exponential backoff: base_seconds * (2 ^ failures), capped at 1 hour
            base_wait = retry_after or 60
            wait_time = min(base_wait * (2 ** min(self.consecutive_failures - 1, 5)), 3600)
            
            self.blocked_until = time.time() + wait_time
            logger.warning(
                f"Rate limit detected. Consecutive failures: {self.consecutive_failures}. "
                f"Pausing requests for {wait_time:.1f}s"
            )
            return wait_time
    
    def record_http_error(self, status_code: int) -> Optional[float]:
        """Record HTTP error and return wait time if rate-limited"""
        with self._lock:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            if status_code == 429:
                logger.warning(f"HTTP 429 Too Many Requests detected")
                wait_time = 60 * (2 ** min(self.consecutive_failures - 1, 5))
                self.blocked_until = time.time() + wait_time
                return wait_time
            
            elif status_code in [401, 403]:
                logger.warning(f"HTTP {status_code} Auth error detected")
                # Auth errors are less severe, shorter wait
                wait_time = 10 + (5 * self.consecutive_failures)
                self.blocked_until = time.time() + wait_time
                return wait_time
            
            elif status_code >= 500:
                logger.warning(f"HTTP {status_code} Server error detected")
                wait_time = 30 * (2 ** min(self.consecutive_failures - 1, 4))
                self.blocked_until = time.time() + wait_time
                return wait_time
            
            return None
    
    def record_success(self):
        """Record successful request"""
        with self._lock:
            self.consecutive_successes += 1
            if self.consecutive_successes > 2:
                # Reset after 3 consecutive successes
                self.consecutive_failures = 0
                if self.blocked_until > time.time():
                    logger.info("Requests recovering, consecutive successes detected")
    
    def reset(self):
        """Reset tracker"""
        with self._lock:
            self.blocked_until = 0.0
            self.consecutive_failures = 0
            self.consecutive_successes = 0
            logger.info("Rate limit tracker reset")
