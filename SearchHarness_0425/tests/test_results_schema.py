"""Tests for results_schema: run spec provenance, envelope assembly,
validation, and volatile-field stripping for byte-level replay diffs."""
from __future__ import annotations

import core.results_schema as rs


def _spec(**kwargs):
    return rs.collect_run_spec(
        benchmark=kwargs.pop("benchmark", "browsecomp"),
        model_id=kwargs.pop("model_id", "model-a"),
        grader_model_id=kwargs.pop("grader_model_id", "model-a"),
        pipeline_config=kwargs.pop("pipeline_config", {"max_iterations": 6}),
        **kwargs,
    )


def _payload(results=None):
    return rs.finalize_payload(
        run_spec=_spec(),
        timestamp="2025-01-01T00:00:00",
        results=results if results is not None else [{"task_index": 0, "is_correct": True}],
        llm_usage={"total": {"calls": 3}},
        metrics={"num_examples": 1, "correct_count": 1, "accuracy": 1.0,
                 "total_elapsed_seconds": 1.5},
    )


class TestRunSpec:
    def test_provenance_keys(self):
        spec = _spec(extra={"seed": 123})
        assert spec["benchmark"] == "browsecomp"
        assert spec["model_id"] == "model-a"
        assert spec["pipeline_config"] == {"max_iterations": 6}
        assert spec["seed"] == 123
        assert "python_version" in spec and "platform" in spec
        assert "git_sha" in spec  # may be None outside a repo

    def test_extra_does_not_clobber_core(self):
        # benchmark/model are positional params here; extra can overwrite,
        # which is intentional for runner-specific fields — guard pipeline_config only.
        spec = _spec(pipeline_config={"a": 1})
        assert spec["pipeline_config"] == {"a": 1}


class TestFinalizePayload:
    def test_envelope_order_and_legacy_keys(self):
        p = _payload()
        assert p["schema_version"] == rs.SCHEMA_VERSION
        assert p["run_spec"]["benchmark"] == "browsecomp"
        # legacy top-level keys preserved verbatim
        assert p["accuracy"] == 1.0 and p["num_examples"] == 1
        assert p["llm_usage"] == {"total": {"calls": 3}}
        assert p["results"] == [{"task_index": 0, "is_correct": True}]
        # envelope comes first, results always last
        keys = list(p)
        assert keys[0] == "schema_version" and keys[1] == "run_spec" and keys[-1] == "results"

    def test_extra_fields_appended(self):
        p = rs.finalize_payload(
            run_spec=_spec(), timestamp="t", results=[], llm_usage=None,
            metrics={"accuracy": 0.0}, extra={"resume": {"enabled": False}},
        )
        assert p["resume"] == {"enabled": False}


class TestValidate:
    def test_valid_payload_has_no_violations(self):
        assert rs.validate_payload(_payload()) == []

    def test_missing_keys_detected(self):
        violations = rs.validate_payload({"accuracy": 0.5})
        assert any("schema_version" in v for v in violations)
        assert any("run_spec" in v for v in violations)
        assert any("results" in v for v in violations)

    def test_wrong_types_detected(self):
        violations = rs.validate_payload({
            "schema_version": 999, "run_spec": "x", "timestamp": "t",
            "accuracy": "high", "results": {},
        })
        assert any("schema_version" in v for v in violations)
        assert any("run_spec is not a dict" in v for v in violations)
        assert any("accuracy is not numeric" in v for v in violations)
        assert any("results is not a list" in v for v in violations)

    def test_not_a_dict(self):
        assert rs.validate_payload([1, 2]) == ["payload is not a dict"]


class TestStripVolatile:
    def test_strips_top_level_and_result_keys(self):
        p = _payload(results=[
            {"task_index": 0, "elapsed_seconds": 9.9, "is_correct": True},
            {"task_index": 1, "elapsed": 3, "is_correct": False},
        ])
        s = rs.strip_volatile(p)
        for key in rs.VOLATILE_TOP_LEVEL:
            assert key not in s
        assert "elapsed_seconds" not in s["results"][0]
        assert "elapsed" not in s["results"][1]
        assert s["results"][0]["is_correct"] is True

    def test_does_not_mutate_input(self):
        p = _payload()
        rs.strip_volatile(p)
        assert "timestamp" in p and "llm_usage" in p

    def test_two_runs_equal_after_strip(self):
        a = _payload()
        b = _payload()
        b["timestamp"] = "2025-01-02T00:00:00"
        b["llm_usage"] = {"total": {"calls": 999}}
        assert rs.strip_volatile(a) == rs.strip_volatile(b)


class TestRunnerWiring:
    def test_runners_import_schema(self):
        import scripts.run.run_browsecomp as run_browsecomp
        import scripts.run.run_browsecomp_fixed_sample as run_browsecomp_fixed_sample
        assert run_browsecomp.rs is rs
        assert run_browsecomp_fixed_sample.rs is rs
