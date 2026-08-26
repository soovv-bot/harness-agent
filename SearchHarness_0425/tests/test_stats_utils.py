"""Tests for stats_utils: bootstrap CI, repeats variance aggregation, formatting."""
from __future__ import annotations

import utils.stats_utils as su


class TestBootstrapCi:
    def test_empty_input(self):
        s = su.bootstrap_ci([])
        assert s["n"] == 0 and s["mean"] is None
        assert s["ci"]["low"] is None and s["ci"]["high"] is None

    def test_single_input_no_resampling(self):
        s = su.bootstrap_ci([1.0])
        assert s["n"] == 1 and s["mean"] == 1.0
        assert s["ci"]["low"] == 1.0 and s["ci"]["high"] == 1.0

    def test_mean_matches_point_estimate(self):
        data = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0]
        s = su.bootstrap_ci([float(x) for x in data])
        assert abs(s["mean"] - 0.6) < 1e-9
        assert s["ci"]["low"] <= s["mean"] <= s["ci"]["high"]

    def test_deterministic_given_seed(self):
        data = [0.0, 1.0] * 25
        a = su.bootstrap_ci(data, n_resamples=500)
        b = su.bootstrap_ci(data, n_resamples=500)
        assert a == b

    def test_ci_within_bounds(self):
        data = [1.0] * 8 + [0.0] * 2  # mean 0.8, small n → wide CI
        s = su.bootstrap_ci(data)
        assert 0.0 <= s["ci"]["low"] <= s["ci"]["high"] <= 1.0

    def test_all_correct_ci_degenerate_at_high(self):
        s = su.bootstrap_ci([1.0] * 20, n_resamples=1000)
        assert s["ci"]["low"] == 1.0 and s["ci"]["high"] == 1.0


class TestAccuracyStats:
    def test_reads_is_correct(self):
        results = [{"is_correct": True}, {"is_correct": False}, {}]
        s = su.accuracy_stats(results)
        assert s["n"] == 3
        assert abs(s["mean"] - 1 / 3) < 1e-9


class TestRepeatsStats:
    def test_empty(self):
        s = su.repeats_stats([])
        assert s["n"] == 0 and s["mean"] is None and s["std"] is None

    def test_spread_fields(self):
        s = su.repeats_stats([0.1, 0.2, 0.3])
        assert s["n"] == 3
        assert abs(s["mean"] - 0.2) < 1e-9
        assert abs(s["std"] - 0.1) < 1e-9
        assert s["min"] == 0.1 and s["max"] == 0.3
        assert s["ci"]["low"] <= s["mean"] <= s["ci"]["high"]

    def test_single_run_zero_std(self):
        s = su.repeats_stats([0.5])
        assert s["std"] == 0.0 and s["min"] == s["max"] == 0.5

    def test_constant_runs_ci_degenerate(self):
        s = su.repeats_stats([0.3, 0.3, 0.3, 0.3])
        assert s["std"] == 0.0


class TestFormatLine:
    def test_percent_line(self):
        s = su.accuracy_stats([{"is_correct": True}] * 6 + [{"is_correct": False}] * 4)
        line = su.format_accuracy_line(s)
        assert "60.0%" in line and "CI" in line and "n=10" in line

    def test_no_results_line(self):
        assert "n/a" in su.format_accuracy_line(su.accuracy_stats([]))

    def test_fraction_line(self):
        s = su.accuracy_stats([{"is_correct": True}] * 3 + [{"is_correct": False}] * 3)
        line = su.format_accuracy_line(s, percent=False)
        assert "0.5" in line and "%" not in line.replace("% CI", " CI")
