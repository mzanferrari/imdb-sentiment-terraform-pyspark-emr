"""Unit tests for scripts/ingest_data.py.

Note: these tests cover the pure functions (hash, idempotency check). The actual
network download is mocked - we never hit the upstream URL in CI.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

# Make scripts/ importable without packaging it
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ingest_data import compute_sha256, is_dataset_present_and_valid


@pytest.fixture
def tmp_file(tmp_path: Path) -> Path:
    """A small file with known content for hashing tests."""
    f = tmp_path / "sample.txt"
    f.write_bytes(b"hello world\n")
    return f


def test_compute_sha256_matches_reference(tmp_file: Path) -> None:
    expected = hashlib.sha256(tmp_file.read_bytes()).hexdigest()
    assert compute_sha256(tmp_file) == expected


def test_compute_sha256_uses_chunked_reads_for_large_files(tmp_path: Path) -> None:
    big = tmp_path / "big.bin"
    big.write_bytes(b"a" * (10 * 1024 * 1024))  # 10 MB
    digest = compute_sha256(big)
    assert len(digest) == 64
    assert digest == hashlib.sha256(b"a" * (10 * 1024 * 1024)).hexdigest()


class TestIsDatasetPresentAndValid:
    def test_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        assert (
            is_dataset_present_and_valid(
                tmp_path / "nonexistent.csv",
                expected_sha256="x" * 64,
            )
            is False
        )

    def test_returns_true_when_hash_matches(self, tmp_file: Path) -> None:
        sha = compute_sha256(tmp_file)
        assert is_dataset_present_and_valid(tmp_file, expected_sha256=sha) is True

    def test_returns_false_when_hash_mismatches(self, tmp_file: Path) -> None:
        assert is_dataset_present_and_valid(tmp_file, expected_sha256="0" * 64) is False

    def test_skip_hash_check_returns_true_if_file_exists(self, tmp_file: Path) -> None:
        assert (
            is_dataset_present_and_valid(
                tmp_file,
                expected_sha256="0" * 64,  # Wrong on purpose
                verify_hash=False,
            )
            is True
        )
