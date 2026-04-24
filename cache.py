"""Einfacher In-Memory Cache mit TTL."""
import time
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    def __init__(self):
        self._store: dict = {}

    def get(self, key: str):
        if key in self._store:
            expires, value = self._store[key]
            if time.time() < expires:
                logger.debug(f"Cache HIT: {key}")
                return value
            del self._store[key]
        return None

    def set(self, key: str, value, ttl_seconds: int = 3600):
        self._store[key] = (time.time() + ttl_seconds, value)
        logger.debug(f"Cache SET: {key} (TTL {ttl_seconds}s)")

    def clear(self):
        self._store.clear()


# Globale Cache-Instanz
cache = SimpleCache()
