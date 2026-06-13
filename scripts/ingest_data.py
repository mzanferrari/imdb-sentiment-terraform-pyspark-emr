"""Automated dataset ingestion script.

Downloads the IMDB sentiment dataset on demand. Idempotent: if a file with the
correct checksum is already present at the target path, the script does nothing.

Why this exists
---------------
The training dataset is too large for git (~63 MB CSV). Storing it in the repo
would bloat clones, conflict with `.gitignore` hygiene, and tie the project to
a specific snapshot of the data. The convention in modern Data Engineering
portfolios is: code is versioned, data is fetched at runtime from a documented
source.

Usage
-----
    python scripts/ingest_data.py
    python scripts/ingest_data.py --force                    # re-download
    python scripts/ingest_data.py --output-dir ./data/       # custom output dir
    python scripts/ingest_data.py --source https://other-url # alternative source URL
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path
from typing import Final

import requests
from tqdm import tqdm

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

# Default source: Stanford NLP IMDB dataset (the original public source).
# A pre-flattened CSV mirror is used here for portfolio convenience. In a
# production setup, you would mirror this to your own S3 bucket with a SHA256
# checksum recorded in the IaC, so the download URL becomes immutable.
DEFAULT_SOURCE_URL: Final[str] = (
    "https://raw.githubusercontent.com/Ankit152/IMDB-sentiment-analysis/master/IMDB-Dataset.csv"
)

# Expected SHA256 of the dataset.csv file. Verify integrity post-download.
# If the upstream file changes, recompute with:
#     sha256sum data/dataset.csv
# This must be updated together with any URL change, in the same commit.
EXPECTED_SHA256: Final[str] = "dfc447764f82be365fa9c2beef4e8df89d3919e3da95f5088004797d79695aa2"

DEFAULT_OUTPUT_DIR: Final[Path] = Path("data")
DEFAULT_FILENAME: Final[str] = "dataset.csv"

CHUNK_SIZE_BYTES: Final[int] = 8192


# ─── LOGGING ──────────────────────────────────────────────────────────────────
#
# Plain text suffices for this standalone script. The pipeline itself
# (src/pipeline/logging_setup.py) uses structured JSON logging via stdlib
# `logging` + a custom JsonFormatter.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest_data")


# ─── CORE ─────────────────────────────────────────────────────────────────────


def compute_sha256(file_path: Path, chunk_size: int = CHUNK_SIZE_BYTES) -> str:
    """Compute SHA256 via chunked reads (memory-safe for large files)."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_dataset_present_and_valid(
    target_path: Path,
    expected_sha256: str,
    *,
    verify_hash: bool = True,
) -> bool:
    """Idempotency check: returns True when no download is needed.

    With verify_hash=False, only existence is checked; otherwise the file's
    SHA256 must match expected_sha256.
    """
    if not target_path.exists():
        logger.info("Dataset not found at %s - will download.", target_path)
        return False

    if not verify_hash:
        logger.info("Dataset found at %s (hash check skipped).", target_path)
        return True

    actual_sha = compute_sha256(target_path)
    if actual_sha == expected_sha256:
        logger.info("Dataset already present at %s with matching SHA256.", target_path)
        return True

    logger.warning(
        "Dataset at %s has unexpected SHA256.\n  expected: %s\n  actual:   %s\nWill re-download.",
        target_path,
        expected_sha256,
        actual_sha,
    )
    return False


def download_with_progress(url: str, target_path: Path, *, timeout: int = 30) -> None:
    """Stream `url` to `target_path` with a progress bar.

    Raises requests.HTTPError on non-2xx responses, OSError if the file can't
    be written.
    """
    logger.info("Downloading from %s -> %s", url, target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total_bytes = int(response.headers.get("content-length", 0))

        with (
            target_path.open("wb") as fh,
            tqdm(
                total=total_bytes,
                unit="B",
                unit_scale=True,
                desc=target_path.name,
                leave=False,
            ) as pbar,
        ):
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE_BYTES):
                if chunk:
                    fh.write(chunk)
                    pbar.update(len(chunk))

    logger.info("Downloaded %s (%s bytes).", target_path.name, target_path.stat().st_size)


def verify_post_download(target_path: Path, expected_sha256: str) -> bool:
    """Verify the downloaded file's hash. Logs warning if mismatched but does not delete.

    Returns False if the hash check fails (caller decides what to do).
    """
    actual = compute_sha256(target_path)
    if actual == expected_sha256:
        logger.info("SHA256 verified: %s", actual)
        return True

    logger.error(
        "SHA256 MISMATCH after download.\n  expected: %s\n  actual:   %s\n"
        "If the source URL is correct, update EXPECTED_SHA256 in this script.",
        expected_sha256,
        actual,
    )
    return False


# ─── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the ingest script."""
    parser = argparse.ArgumentParser(
        description="Idempotently download the IMDB sentiment dataset for local pipeline runs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE_URL,
        help="Source URL to download from.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the dataset will be saved.",
    )
    parser.add_argument(
        "--filename",
        default=DEFAULT_FILENAME,
        help="Local filename for the downloaded dataset.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download even if the file already exists with a valid hash.",
    )
    parser.add_argument(
        "--skip-hash-check",
        action="store_true",
        help="Skip SHA256 verification (NOT recommended outside of development).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Download the dataset if absent or stale; return process exit code."""
    args = parse_args(argv)
    target_path = args.output_dir / args.filename

    if not args.force and is_dataset_present_and_valid(
        target_path,
        EXPECTED_SHA256,
        verify_hash=not args.skip_hash_check,
    ):
        logger.info("Nothing to do.")
        return 0

    try:
        download_with_progress(args.source, target_path)
    except requests.HTTPError as exc:
        logger.exception("HTTP error during download: %s", exc)
        return 1
    except OSError as exc:
        logger.exception("Filesystem error: %s", exc)
        return 1

    if not args.skip_hash_check and not verify_post_download(target_path, EXPECTED_SHA256):
        logger.error(
            "Downloaded file failed integrity check. File is kept for inspection at %s.",
            target_path,
        )
        return 2

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
