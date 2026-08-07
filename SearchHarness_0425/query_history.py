"""
Query History Memory

Records structured history of all search queries executed during a search task.
Each entry captures the query context, results, and lightweight quality signals.

This module is passive — it only records. Active features like deduplication,
query critique, and planning feedback will be built on top of this.
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class QueryRecord:
    """A single query history entry."""

    def __init__(
        self,
        query: str,
        phase: str,
        subtask: str,
        results_summary: str = "",
        new_source_families: Optional[List[str]] = None,
        new_candidates: Optional[List[str]] = None,
        result_quality: str = "unknown",
        led_to_crawl: bool = False,
        crawl_urls: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            query: The search query text that was executed.
            phase: The planning phase when this query was made
                (source_identification, candidate_generation, etc.).
            subtask: The subtask this query was part of.
            results_summary: Brief summary of what the search returned.
            new_source_families: List of source families/domains discovered
                that had not appeared in prior queries.
            new_candidates: List of candidate entities/answers discovered
                that had not appeared in prior queries.
            result_quality: Quality signal — one of:
                "empty" (no results),
                "noise" (results irrelevant),
                "low" (weakly relevant),
                "medium" (some useful results),
                "high" (directly useful results),
                "unknown" (not yet assessed).
            led_to_crawl: Whether this search led to a valuable crawl action.
            crawl_urls: URLs that were crawled as a result of this search.
            metadata: Arbitrary additional metadata.
        """
        self.query = query
        self.phase = phase
        self.subtask = subtask
        self.results_summary = results_summary
        self.new_source_families = new_source_families or []
        self.new_candidates = new_candidates or []
        self.result_quality = result_quality
        self.led_to_crawl = led_to_crawl
        self.crawl_urls = crawl_urls or []
        self.metadata = metadata or {}

        self.timestamp = datetime.now().isoformat()
        self.turn_index: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "phase": self.phase,
            "subtask": self.subtask,
            "results_summary": self.results_summary,
            "new_source_families": self.new_source_families,
            "new_candidates": self.new_candidates,
            "result_quality": self.result_quality,
            "led_to_crawl": self.led_to_crawl,
            "crawl_urls": self.crawl_urls,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "turn_index": self.turn_index,
        }


class QueryHistoryMemory:
    """
    Maintains a structured history of search queries for a single task.

    Usage:
        memory = QueryHistoryMemory()
        memory.record(
            query="Albrecht Penck glacial studies",
            phase="source_identification",
            subtask="Identify the European earth scientist",
            results_summary="Found Wikipedia article for Albrecht Penck",
            new_source_families=["wikipedia.org"],
            new_candidates=["Albrecht Penck"],
            result_quality="high",
        )
        memory.save("data/query_history/task_001.json")
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.records: List[QueryRecord] = []
        self._known_source_families: set = set()
        self._known_candidates: set = set()
        self._query_texts: set = set()

    @property
    def source_families(self) -> List[str]:
        """All unique source families seen so far."""
        return sorted(self._known_source_families)

    @property
    def candidates(self) -> List[str]:
        """All unique candidates seen so far."""
        return sorted(self._known_candidates)

    @property
    def queries(self) -> List[str]:
        """All unique query texts seen so far."""
        return sorted(self._query_texts)

    def record(self, *args, **kwargs):
        with self._lock:
            return self._record_impl(*args, **kwargs)

    def _record_impl(
        self,
        query: str,
        phase: str,
        subtask: str,
        results_summary: str = "",
        new_source_families: Optional[List[str]] = None,
        new_candidates: Optional[List[str]] = None,
        result_quality: str = "unknown",
        led_to_crawl: bool = False,
        crawl_urls: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QueryRecord:
        """
        Record a search query.

        Args:
            query: The search query text.
            phase: Current planning phase.
            subtask: Current subtask description.
            results_summary: Brief summary of search results.
            new_source_families: Newly discovered source families/domains.
            new_candidates: Newly discovered candidate entities.
            result_quality: Quality signal.
            led_to_crawl: Whether this led to a crawl.
            crawl_urls: URLs crawled as a follow-up.
            metadata: Additional metadata.

        Returns:
            The created QueryRecord.
        """
        entry = QueryRecord(
            query=query,
            phase=phase,
            subtask=subtask,
            results_summary=results_summary,
            new_source_families=new_source_families,
            new_candidates=new_candidates,
            result_quality=result_quality,
            led_to_crawl=led_to_crawl,
            crawl_urls=crawl_urls,
            metadata=metadata,
        )
        entry.turn_index = len(self.records)

        self.records.append(entry)
        self._query_texts.add(query.strip().lower())

        if new_source_families:
            self._known_source_families.update(sf.strip().lower() for sf in new_source_families)

        if new_candidates:
            self._known_candidates.update(c.strip() for c in new_candidates)

        logger.debug(
            f"[QueryHistory] #{entry.turn_index} query='{query[:60]}...' "
            f"phase={phase} quality={result_quality}"
        )

        return entry

    def update_last_record(self, *args, **kwargs):
        with self._lock:
            return self._update_last_record_impl(*args, **kwargs)

    def _update_last_record_impl(
        self,
        results_summary: Optional[str] = None,
        new_source_families: Optional[List[str]] = None,
        new_candidates: Optional[List[str]] = None,
        result_quality: Optional[str] = None,
        led_to_crawl: Optional[bool] = None,
        crawl_urls: Optional[List[str]] = None,
    ):
        """
        Update the most recent record (e.g., after crawl results come back).

        This is useful when a search is recorded first, then the downstream
        crawl provides additional information to annotate the record.
        """
        if not self.records:
            return

        last = self.records[-1]
        if results_summary is not None:
            last.results_summary = results_summary
        if new_source_families is not None:
            last.new_source_families = new_source_families
            self._known_source_families.update(sf.strip().lower() for sf in new_source_families)
        if new_candidates is not None:
            last.new_candidates = new_candidates
            self._known_candidates.update(c.strip() for c in new_candidates)
        if result_quality is not None:
            last.result_quality = result_quality
        if led_to_crawl is not None:
            last.led_to_crawl = led_to_crawl
        if crawl_urls is not None:
            last.crawl_urls = crawl_urls

    def add_candidates_to_last_record(self, candidates: Optional[List[str]]) -> None:
        with self._lock:
            return self._add_candidates_to_last_record_impl(candidates)

    def _add_candidates_to_last_record_impl(self, candidates: Optional[List[str]]) -> None:
        """Merge newly surfaced candidates into the most recent query record."""
        if not self.records or not candidates:
            return
        last = self.records[-1]
        existing = {str(c).strip().lower() for c in last.new_candidates}
        for candidate in candidates:
            name = str(candidate).strip()
            key = name.lower()
            if not name or key in existing:
                continue
            last.new_candidates.append(name)
            existing.add(key)
            self._known_candidates.add(name)

    def to_dict(self) -> Dict:
        """Serialize the full history to a dict."""
        return {
            "total_queries": len(self.records),
            "unique_source_families": self.source_families,
            "unique_candidates": self.candidates,
            "records": [r.to_dict() for r in self.records],
        }

    def save(self, path: str):
        """Save history to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Saved query history to {path} ({len(self.records)} records)")

    @classmethod
    def load(cls, path: str) -> "QueryHistoryMemory":
        """Load history from a JSON file."""
        p = Path(path)
        if not p.exists():
            return cls()

        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)

        memory = cls()
        memory._known_source_families = set(sf.lower() for sf in data.get("unique_source_families", []))
        memory._known_candidates = set(data.get("unique_candidates", []))

        for rec in data.get("records", []):
            entry = QueryRecord(
                query=rec["query"],
                phase=rec["phase"],
                subtask=rec["subtask"],
                results_summary=rec.get("results_summary", ""),
                new_source_families=rec.get("new_source_families", []),
                new_candidates=rec.get("new_candidates", []),
                result_quality=rec.get("result_quality", "unknown"),
                led_to_crawl=rec.get("led_to_crawl", False),
                crawl_urls=rec.get("crawl_urls", []),
                metadata=rec.get("metadata", {}),
            )
            entry.timestamp = rec.get("timestamp", "")
            entry.turn_index = rec.get("turn_index", len(memory.records))
            memory.records.append(entry)
            memory._query_texts.add(rec["query"].strip().lower())

        logger.info(f"Loaded query history from {path} ({len(memory.records)} records)")
        return memory

    def __len__(self):
        return len(self.records)

    def __repr__(self):
        return f"QueryHistoryMemory(records={len(self.records)}, sources={len(self._known_source_families)}, candidates={len(self._known_candidates)})"
