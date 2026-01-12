import time
from typing import Any, Optional
import os

class SimpleCache:
    def __init__(self, ttl: int = None):
        default_ttl = int(os.getenv("CACHE_TTL", "3600") or 3600)
        self.cache = {}
        self.ttl = ttl if ttl is not None else default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        item = self.cache.get(key)
        if not item:
            return None
        value, expiry = item
        if time.time() < expiry:
            return value
        # expired
        self.cache.pop(key, None)
        return None

    def set(self, key: str, value: Any):
        """Set value in cache with TTL"""
        expiry = time.time() + self.ttl
        self.cache[key] = (value, expiry)

    def clear(self):
        """Clear all cache"""
        self.cache.clear()
