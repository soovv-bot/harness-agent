"""Tests for run_checkpoint (M0 T4): save/skip/thread-safety/tamper-resilience."""
from __future__ import annotations

import json
import threading

from scripts.run.run_checkpoint import DEFAULT_GOOD_STATUSES, RunCheckpoint


def _result(pos: int, status: str = "completed") -> dict:
    return {"sample_position": pos, "is_correct": pos % 2 == 0, "pipeline_status": status}


class TestRunCheckpoint:
    def test_fresh_checkpoint_empty(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        assert cp.count() == 0
        skip, run = cp.positions_to_skip([1, 2, 3])
        assert skip == []
        assert run == [1, 2, 3]

    def test_save_and_skip(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        cp.save_position(1, _result(1))
        cp.save_position(3, _result(3))
        skip, run = cp.positions_to_skip([1, 2, 3, 4])
        assert skip == [1, 3]
        assert run == [2, 4]

    def test_persistence_across_instances(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        cp.save_position(2, _result(2))
        cp2 = RunCheckpoint(tmp_path / "c.json")
        assert cp2.count() == 1
        assert cp2.get_result(2)["sample_position"] == 2

    def test_error_status_is_rerun(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        cp.save_position(1, _result(1, status="completed"))
        cp.save_position(2, _result(2, status="error"))
        cp.save_position(3, _result(3, status="max_turns_reached"))
        skip, run = cp.positions_to_skip([1, 2, 3])
        assert skip == [1]
        assert run == [2, 3]

    def test_custom_good_statuses(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        cp.save_position(1, _result(1, status="weird"))
        skip, run = cp.positions_to_skip([1], good_statuses={"weird"})
        assert skip == [1]
        assert run == []

    def test_default_status_inference(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        cp.save_position(5, {"pipeline_status": "completed"})
        skip, run = cp.positions_to_skip([5])
        assert skip == [5]

    def test_corrupt_sidecar_recovers(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text("{not valid json", encoding="utf-8")
        cp = RunCheckpoint(p)
        assert cp.count() == 0
        cp.save_position(1, _result(1))
        assert cp.count() == 1
        # And the rewritten file is now valid JSON.
        json.loads(p.read_text(encoding="utf-8"))

    def test_for_output_sidecar_naming(self, tmp_path):
        out = tmp_path / "results" / "run.json"
        cp = RunCheckpoint.for_output(out)
        assert cp.path.name == "run.json.checkpoint.json"
        assert cp.path.parent == out.parent

    def test_thread_safe_concurrent_saves(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")

        def save(n: int) -> None:
            for i in range(50):
                cp.save_position(n * 1000 + i, _result(n))

        threads = [threading.Thread(target=save, args=(i,)) for i in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert cp.count() == 200
        # File must be parseable after concurrent writes (atomic replaces).
        payload = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
        assert len(payload["positions"]) == 200

    def test_summary_counts(self, tmp_path):
        cp = RunCheckpoint(tmp_path / "c.json")
        cp.save_position(1, _result(1, "completed"))
        cp.save_position(2, _result(2, "completed"))
        cp.save_position(3, _result(3, "error"))
        s = cp.summary()
        assert s["completed"] == 2
        assert s["error"] == 1

    def test_good_statuses_constant(self):
        assert "completed" in DEFAULT_GOOD_STATUSES
        assert "error" not in DEFAULT_GOOD_STATUSES
