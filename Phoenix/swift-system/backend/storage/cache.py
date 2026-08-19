"""
SWIFT SYSTEM - Cache Layer Interface
Provides in-memory fast caching interface with Redis-compatible fallbacks.
"""

from typing import Any, Optional
import time


class SwiftCache:
    def __init__(self):
        self._cache = {}
        self._ttl = {}

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        self._cache[key] = value
        if ttl_seconds is not None:
            self._ttl[key] = time.time() + ttl_seconds
        elif key in self._ttl:
            del self._ttl[key]

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._ttl and time.time() > self._ttl[key]:
            del self._cache[key]
            del self._ttl[key]
            return default
        return self._cache.get(key, default)

    def delete(self, key: str):
        self._cache.pop(key, None)
        self._ttl.pop(key, None)


cache = SwiftCache()
