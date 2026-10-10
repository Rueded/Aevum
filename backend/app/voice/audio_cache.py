"""Ephemeral in-memory audio cache with canonical identity and TTL eviction (Phase 10.3).

Governed by ADR-021:
- Lock E: Canonical Audio Cache Identity:
  - Cache entries are keyed strictly by compute_canonical_audio_cache_key().
  - Prevents collisions across text, voice profiles, formats, and emotional prosody variations.
- Lock F: Ephemeral Media Lifecycle Isolation:
  - Audio cache manages transient media artifacts only (CREATED -> ACTIVE -> EXPIRED -> PURGED).
  - Cache expiration, eviction, or purge strictly never triggers cascade deletion or mutation
    of conversation records, biography facts, or canonical reality state.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.voice.voice_models import AudioData, AudioMediaLifecycle


@dataclass
class AudioCacheEntry:
    """Internal cache entry holding transient audio payload and lifecycle metadata."""

    cache_key: str
    audio: AudioData
    created_at: datetime
    last_accessed_at: datetime
    ttl_seconds: int
    lifecycle_state: AudioMediaLifecycle = AudioMediaLifecycle.ACTIVE

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check if entry has exceeded its time-to-live."""
        current_time = now or datetime.now(timezone.utc)
        elapsed = (current_time - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds


class AudioCache:
    """Ephemeral, memory-bounded LRU cache for synthesized audio artifacts.

    Enforces Lock F: strictly independent ephemeral media store with zero database coupling.
    """

    def __init__(
        self,
        max_entries: int = 256,
        default_ttl_seconds: int = 3600,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1.")
        if default_ttl_seconds < 1:
            raise ValueError("default_ttl_seconds must be at least 1.")

        self._max_entries = max_entries
        self._default_ttl_seconds = default_ttl_seconds
        self._entries: OrderedDict[str, AudioCacheEntry] = OrderedDict()

    @property
    def current_size(self) -> int:
        """Return the number of entries currently stored in cache."""
        return len(self._entries)

    def get(self, cache_key: str, now: Optional[datetime] = None) -> Optional[AudioData]:
        """Retrieve audio from cache if present and unexpired.

        Updates LRU access order and last_accessed_at on hit.
        """
        if cache_key not in self._entries:
            return None

        entry = self._entries[cache_key]
        current_time = now or datetime.now(timezone.utc)

        if entry.is_expired(current_time):
            entry.lifecycle_state = AudioMediaLifecycle.EXPIRED
            # Remove expired entry from active map
            del self._entries[cache_key]
            return None

        # Move to end for LRU policy
        self._entries.move_to_end(cache_key)
        entry.last_accessed_at = current_time
        return entry.audio

    def put(
        self,
        cache_key: str,
        audio: AudioData,
        ttl_seconds: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> None:
        """Store audio payload in cache under the canonical cache key.

        Evicts least-recently-used entry if capacity is exceeded.
        """
        current_time = now or datetime.now(timezone.utc)
        effective_ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds

        if effective_ttl < 1:
            raise ValueError("ttl_seconds must be at least 1.")

        # If already exists, update entry
        if cache_key in self._entries:
            entry = self._entries[cache_key]
            entry.audio = audio
            entry.last_accessed_at = current_time
            entry.created_at = current_time
            entry.ttl_seconds = effective_ttl
            entry.lifecycle_state = AudioMediaLifecycle.ACTIVE
            self._entries.move_to_end(cache_key)
            return

        # Evict oldest entry if capacity reached
        if len(self._entries) >= self._max_entries:
            oldest_key, oldest_entry = self._entries.popitem(last=False)
            oldest_entry.lifecycle_state = AudioMediaLifecycle.PURGED

        new_entry = AudioCacheEntry(
            cache_key=cache_key,
            audio=audio,
            created_at=current_time,
            last_accessed_at=current_time,
            ttl_seconds=effective_ttl,
            lifecycle_state=AudioMediaLifecycle.ACTIVE,
        )
        self._entries[cache_key] = new_entry

    def evict_expired(self, now: Optional[datetime] = None) -> int:
        """Scan and purge all expired entries. Returns count of purged items."""
        current_time = now or datetime.now(timezone.utc)
        keys_to_remove = [
            key for key, entry in self._entries.items() if entry.is_expired(current_time)
        ]
        for key in keys_to_remove:
            entry = self._entries.pop(key)
            entry.lifecycle_state = AudioMediaLifecycle.EXPIRED
        return len(keys_to_remove)

    def purge_all(self) -> int:
        """Purge all stored cache entries (ADR-021 Lock F: zero domain mutation)."""
        count = len(self._entries)
        for entry in self._entries.values():
            entry.lifecycle_state = AudioMediaLifecycle.PURGED
        self._entries.clear()
        return count
