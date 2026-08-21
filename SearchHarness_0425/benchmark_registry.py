"""Declarative benchmark registry.

Single source of truth for benchmark metadata: dataset URL, local cache
location, canary-based decryption, and example decoding. Runners look specs up
by name instead of hardcoding paths/URLs, so adding a new benchmark means
registering one more spec.

Usage:
    from benchmark_registry import get_benchmark
    spec = get_benchmark("browsecomp")
    examples = spec.load_examples()              # caches CSV on first fetch
    question = spec.decode_field(example, "problem")
    answer = spec.decode_field(example, "answer")
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parent


# ── canary XOR decryption (BrowseComp ships canary-encrypted fields) ────


def _derive_key(password: str, length: int) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(password.encode())
    key = hasher.digest()
    return key * (length // len(key)) + key[: length % len(key)]


def decrypt_field(ciphertext_b64: str, password: str) -> str:
    encrypted = base64.b64decode(ciphertext_b64)
    key = _derive_key(password, len(encrypted))
    return bytes(a ^ b for a, b in zip(encrypted, key)).decode()


def encrypt_field(plaintext: str, password: str) -> str:
    """Inverse of decrypt_field — used by tests/fixtures only."""
    raw = plaintext.encode()
    key = _derive_key(password, len(raw))
    return base64.b64encode(bytes(a ^ b for a, b in zip(raw, key))).decode()


# ── spec ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    display_name: str
    dataset_url: str
    cache_relpath: str
    canary_field: str = "canary"
    encrypted_fields: Tuple[str, ...] = ("problem", "answer")
    id_field: str = ""  # stable example id column, if the dataset has one

    @property
    def cache_path(self) -> Path:
        return _REPO_ROOT / self.cache_relpath

    def load_examples(self, use_cache: bool = True):
        """Load raw dataset rows as dicts, caching the CSV on first download."""
        cache = self.cache_path
        if use_cache and cache.exists():
            logger.info(f"Using cached {self.display_name} dataset: {cache}")
            df = pd.read_csv(cache)
        else:
            logger.info(f"Downloading {self.display_name} dataset...")
            df = pd.read_csv(self.dataset_url)
            cache.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            logger.info(f"Cached {self.display_name} dataset to: {cache}")
        return [row.to_dict() for _, row in df.iterrows()]

    def decode_field(self, example: Dict, field: str) -> str:
        """Plaintext for an encrypted field; plaintext passthrough for others."""
        value = example.get(field, "")
        if field in self.encrypted_fields:
            return decrypt_field(value, example.get(self.canary_field, ""))
        return value if isinstance(value, str) else str(value)


BROWSECOMP = BenchmarkSpec(
    name="browsecomp",
    display_name="BrowseComp",
    dataset_url="https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv",
    cache_relpath="docs/browse_comp_test_set.csv",
)

_REGISTRY: Dict[str, BenchmarkSpec] = {spec.name: spec for spec in (BROWSECOMP,)}


def get_benchmark(name: str) -> BenchmarkSpec:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise KeyError(f"Unknown benchmark {name!r}; registered: {known}") from None


def list_benchmarks() -> List[BenchmarkSpec]:
    return list(_REGISTRY.values())
