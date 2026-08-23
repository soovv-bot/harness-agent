"""Tests for the unified run_benchmark.py CLI dispatch."""
from __future__ import annotations

import sys

import pytest

import scripts.run.run_benchmark as rb


def _run(argv):
    old = sys.argv[:]
    sys.argv = ["run_benchmark.py", *argv]
    try:
        rb.main()
    finally:
        sys.argv = old


class TestList:
    def test_list_shows_registry(self, capsys):
        _run(["--list"])
        out = capsys.readouterr().out
        assert "browsecomp" in out and "BrowseComp" in out
        assert "sample" in out and "fixed" in out and "repeats" in out


class TestDispatch:
    def test_sample_mode_forwards_args(self, capsys):
        with pytest.raises(SystemExit) as ei:  # argparse --help exits 0
            _run(["browsecomp", "sample", "--help"])
        assert ei.value.code == 0
        assert "--num-examples" in capsys.readouterr().out

    def test_fixed_mode_forwards_args(self, capsys):
        with pytest.raises(SystemExit) as ei:
            _run(["browsecomp", "fixed", "--help"])
        assert ei.value.code == 0
        assert "--positions" in capsys.readouterr().out

    def test_repeats_mode_forwards_args(self, capsys):
        with pytest.raises(SystemExit) as ei:
            _run(["browsecomp", "repeats", "--help"])
        assert ei.value.code == 0
        assert "--repeats" in capsys.readouterr().out

    def test_unknown_benchmark_names_registered(self):
        with pytest.raises(KeyError, match="browsecomp"):
            _run(["hotpotqa", "sample"])

    def test_unknown_mode_rejected_by_argparse(self):
        with pytest.raises(SystemExit) as ei:
            _run(["browsecomp", "bogus"])
        assert ei.value.code == 2

    def test_missing_args_errors(self):
        with pytest.raises(SystemExit) as ei:
            _run([])
        assert ei.value.code == 2
