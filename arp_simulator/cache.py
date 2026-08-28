from __future__ import annotations

import threading
import time

from .models import ArpCacheEntry, CacheChange


class ArpCache:
    def __init__(self, aging_seconds: float = 30.0, clock=time.monotonic):
        self.aging_seconds = aging_seconds
        self._clock = clock
        self._entries: dict[str, ArpCacheEntry] = {}
        self._lock = threading.RLock()

    def learn(self, ip: str, mac: str, now: float | None = None) -> tuple[ArpCacheEntry, CacheChange]:
        now = self._clock() if now is None else now
        with self._lock:
            old = self._entries.get(ip)
            change = CacheChange.NEW if old is None else (
                CacheChange.UPDATED if old.mac != mac else CacheChange.HIT
            )
            entry = ArpCacheEntry(ip, mac, old.learned_at if old else now, now, change)
            self._entries[ip] = entry
            return entry, change

    def lookup(self, ip: str, now: float | None = None) -> ArpCacheEntry | None:
        now = self._clock() if now is None else now
        with self._lock:
            entry = self._entries.get(ip)
            if entry is None or now - entry.last_seen >= self.aging_seconds:
                if entry is not None:
                    del self._entries[ip]
                return None
            entry.last_seen = now
            entry.state = CacheChange.HIT
            return entry

    def expire(self, now: float | None = None) -> list[ArpCacheEntry]:
        now = self._clock() if now is None else now
        expired: list[ArpCacheEntry] = []
        with self._lock:
            for ip, entry in list(self._entries.items()):
                if now - entry.last_seen >= self.aging_seconds:
                    entry.state = CacheChange.EXPIRED
                    expired.append(entry)
                    del self._entries[ip]
        return expired

    def snapshot(self, now: float | None = None) -> list[ArpCacheEntry]:
        now = self._clock() if now is None else now
        with self._lock:
            return [ArpCacheEntry(e.ip, e.mac, e.learned_at, e.last_seen, e.state) for e in self._entries.values() if now - e.last_seen < self.aging_seconds]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def shift_timestamps(self, seconds: float) -> None:
        """Exclude paused wall-clock time from entry aging."""
        with self._lock:
            for entry in self._entries.values():
                entry.learned_at += seconds
                entry.last_seen += seconds
