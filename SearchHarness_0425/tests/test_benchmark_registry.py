"""Tests for benchmark_registry: spec lookup, canary crypto roundtrip,
cache-aware dataset loading, and runner wiring identity."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

import core.benchmark_registry as br


@pytest.fixture
def spec(tmp_path, monkeypatch):
    """A clone of the BrowseComp spec whose cache path lives in tmp_path."""
    monkeypatch.setattr(br, "_REPO_ROOT", tmp_path)
    return replace(br.BROWSECOMP)


class TestRegistryLookup:
    def test_browsecomp_registered(self):
        spec = br.get_benchmark("browsecomp")
        assert spec is br.BROWSECOMP
        assert spec.display_name == "BrowseComp"
        assert "browse_comp_test_set.csv" in spec.dataset_url

    def test_unknown_name_raises_with_known_list(self):
        with pytest.raises(KeyError, match="browsecomp"):
            br.get_benchmark("hotpotqa")

    def test_list_benchmarks(self):
        names = [s.name for s in br.list_benchmarks()]
        assert names == ["browsecomp"]


class TestCanaryCrypto:
    def test_roundtrip(self):
        canary = "test-canary-123"
        plaintext = "问题：谁是李四？答案是中文 ✓"
        ciphertext = br.encrypt_field(plaintext, canary)
        assert ciphertext != plaintext
        assert br.decrypt_field(ciphertext, canary) == plaintext

    def test_wrong_canary_never_matches(self):
        ciphertext = br.encrypt_field("hello", "canary-a")
        try:
            result = br.decrypt_field(ciphertext, "canary-b")
        except UnicodeDecodeError:
            return  # garbled bytes that aren't valid UTF-8 — acceptable
        assert result != "hello"

    def test_run_browsecomp_reexports(self):
        from scripts.run.run_browsecomp import _decrypt, _derive_key  # noqa: F401

        assert _decrypt is br.decrypt_field


class TestLoadExamples:
    def _write_df(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(path, index=False)

    def test_uses_local_cache_without_download(self, spec, monkeypatch):
        canary = "c1"
        self._write_df(spec.cache_path, [{
            "canary": canary,
            "problem": br.encrypt_field("Q1", canary),
            "answer": br.encrypt_field("A1", canary),
        }])

        original_read_csv = pd.read_csv

        def guarded_read_csv(src, *a, **k):
            if str(src).startswith("http"):
                raise AssertionError("must not download")
            return original_read_csv(src, *a, **k)

        monkeypatch.setattr(pd, "read_csv", guarded_read_csv)

        rows = spec.load_examples()
        assert len(rows) == 1
        assert spec.decode_field(rows[0], "problem") == "Q1"
        assert spec.decode_field(rows[0], "answer") == "A1"

    def test_downloads_and_caches_when_missing(self, spec, monkeypatch):
        canary = "c2"
        fake_df = pd.DataFrame([{
            "canary": canary,
            "problem": br.encrypt_field("Q2", canary),
            "answer": br.encrypt_field("A2", canary),
        }])
        monkeypatch.setattr(pd, "read_csv", lambda src, *a, **k: fake_df.copy())
        rows = spec.load_examples()
        assert spec.cache_path.exists()
        assert spec.decode_field(rows[0], "problem") == "Q2"

    def test_decode_field_passthrough_for_plaintext(self, spec):
        row = {"canary": "c", "problem": "enc", "answer": "enc", "notes": "plain"}
        assert spec.decode_field(row, "notes") == "plain"


class TestRunnerWiring:
    def test_both_runners_use_same_spec(self):
        import scripts.run.run_browsecomp as run_browsecomp
        import scripts.run.run_browsecomp_fixed_sample as run_browsecomp_fixed_sample

        assert run_browsecomp.get_benchmark("browsecomp") is br.BROWSECOMP
        assert run_browsecomp_fixed_sample.get_benchmark("browsecomp") is br.BROWSECOMP
