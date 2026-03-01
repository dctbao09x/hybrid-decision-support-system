"""Market cache loader used by scoring.

This module guarantees scoring reads market data from cache only.
No realtime API calls are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class CacheMeta:
    updated_at: Optional[datetime]
    entries_count: int
    fresh: bool
    max_age_hours: int


class MarketCacheLoader:
    """Reads and indexes market cache for deterministic scoring usage."""

    def __init__(self, cache_path: Optional[Path] = None):
        root = Path(__file__).resolve().parents[2]
        self.cache_path = cache_path or (root / "data" / "market_cache.json")
        self._lock = RLock()
        self._cache_doc: Dict[str, Any] = {"version": "1.0", "updated_at": None, "entries": []}
        self._index_by_title: Dict[str, Dict[str, Any]] = {}
        self._last_loaded_mtime: Optional[float] = None

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if not self.cache_path.exists():
                logger.warning("Market cache file not found: %s", self.cache_path)
                self._cache_doc = {"version": "1.0", "updated_at": None, "entries": []}
                self._index_by_title = {}
                self._last_loaded_mtime = None
                return self._cache_doc

            mtime = self.cache_path.stat().st_mtime
            if self._last_loaded_mtime is not None and mtime == self._last_loaded_mtime:
                return self._cache_doc

            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            entries = raw.get("entries") or []
            if not isinstance(entries, list):
                entries = []

            self._cache_doc = {
                "version": str(raw.get("version", "1.0")),
                "updated_at": raw.get("updated_at"),
                "entries": entries,
            }
            self._index_by_title = self._build_index(entries)
            self._last_loaded_mtime = mtime

            logger.info(
                "Market cache loaded | path=%s | entries=%s",
                self.cache_path,
                len(entries),
            )
            return self._cache_doc

    def meta(self, max_age_hours: int = 24) -> CacheMeta:
        doc = self.load()
        updated_at_raw = doc.get("updated_at")
        parsed: Optional[datetime] = None
        fresh = False
        if isinstance(updated_at_raw, str):
            try:
                parsed = _parse_iso(updated_at_raw)
                fresh = parsed >= (_utc_now() - timedelta(hours=max_age_hours))
            except ValueError:
                parsed = None
                fresh = False

        return CacheMeta(
            updated_at=parsed,
            entries_count=len(doc.get("entries") or []),
            fresh=fresh,
            max_age_hours=max_age_hours,
        )

    def lookup_by_title(self, career_name: str) -> Optional[Dict[str, Any]]:
        self.load()
        key = (career_name or "").strip().lower()
        if not key:
            return None
        return self._index_by_title.get(key)

    @staticmethod
    def _build_index(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            payload = entry.get("payload") or {}
            jobs = payload.get("jobs") or []
            if not isinstance(jobs, list):
                continue
            for job in jobs:
                title = str(job.get("title") or "").strip().lower()
                if title and title not in index:
                    index[title] = job
        return index
