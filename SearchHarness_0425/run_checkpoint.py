"""Position-granular result checkpointing for resumable evaluation runs (T4, M0).

A :class:`RunCheckpoint` persists per-position results to a sidecar JSON file
next to the run's output file, so an interrupted run (Ctrl+C / crash / rate
limit) can be resumed: positions with an acceptable stored status are skipped,
the rest are re-run and merged back in.

Design
------
- Sidecar layout::

    {
      "schema": 1,
      "output_file": "results/browsecomp_fixed.json",
      "positions": {"3": {"status": "completed", "result": {...}, "saved_at": "..."}},
    }

- Thread-safe ``save_position`` (single lock, atomic file replace via tmp file).
- ``load_completed(positions, good_statuses)`` → positions to skip.
- The final merged results list preserves the original 1-indexed positions.

This module is runner-agnostic: ``run_browsecomp_fixed_sample.py`` uses it for
per-sample checkpointing and ``run_seed_repeats.py`` uses it for per-run-index
checkpointing.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = 1

# Statuses that count as "done" — anything else is re-run on resume.
# Mirrors the parent-repo rule: only max-turns / hard error conditions retry;
# a wrong-but-complete answer is final (grading is non-deterministic to redo).
DEFAULT_GOOD_STATUSES = frozenset({
    "completed",
    "correct",
    "incorrect",
    "grader_undetermined",
    "ok",
})


class RunCheckpoint:
    """Sidecar-file checkpoint for position-granular resume."""

    def __init__(self, path: Path, output_file: str = "") -> None:
        self.path = Path(path)
        self.output_file = output_file
        self._lock = threading.Lock()
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._load()

    @classmethod
    def for_output(cls, output_file: Path | str) -> "RunCheckpoint":
        """Checkpoint colocated with an output file: ``<name>.checkpoint.json``."""
        out = Path(output_file)
        sidecar = out.with_suffix(out.suffix + ".checkpoint.json")
        return cls(sidecar, output_file=str(out))

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            self._positions = {}
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._positions = payload.get("positions", {}) or {}
        except Exception:
            # Corrupt sidecar → start fresh rather than crash the run.
            self._positions = {}

    def _write(self) -> None:
        payload = {
            "schema": SCHEMA_VERSION,
            "output_file": self.output_file,
            "updated_at": datetime.now().isoformat(),
            "positions": self._positions,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # -- API ----------------------------------------------------------------

    def save_position(self, position: int, result: Dict[str, Any], status: str = "") -> None:
        """Record a finished position. ``status`` defaults to the result's own
        ``pipeline_status`` field."""
        resolved = status or str(result.get("pipeline_status") or result.get("status") or "completed")
        with self._lock:
            self._positions[str(position)] = {
                "status": resolved,
                "result": result,
                "saved_at": datetime.now().isoformat(),
            }
            self._write()

    def positions_to_skip(
        self,
        positions: Iterable[int],
        good_statuses: Optional[Iterable[str]] = None,
    ) -> Tuple[List[int], List[int]]:
        """Split ``positions`` into (to_skip, to_run) based on stored statuses.

        A position is skipped iff it has a stored entry whose status is in
        ``good_statuses`` (default :data:`DEFAULT_GOOD_STATUSES`).
        """
        good = set(good_statuses) if good_statuses is not None else set(DEFAULT_GOOD_STATUSES)
        skip: List[int] = []
        run: List[int] = []
        with self._lock:
            for pos in positions:
                entry = self._positions.get(str(pos))
                if entry is not None and str(entry.get("status", "")) in good:
                    skip.append(pos)
                else:
                    run.append(pos)
        return skip, run

    def get_result(self, position: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._positions.get(str(position))
            return dict(entry["result"]) if entry is not None else None

    def summary(self) -> Dict[str, int]:
        with self._lock:
            counts: Dict[str, int] = {}
            for entry in self._positions.values():
                s = str(entry.get("status", ""))
                counts[s] = counts.get(s, 0) + 1
            return counts

    def count(self) -> int:
        with self._lock:
            return len(self._positions)
