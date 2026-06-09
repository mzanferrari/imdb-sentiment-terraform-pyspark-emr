"""Shared pytest fixtures.

A single SparkSession is created once per test module and reused. Spark startup
is expensive (~5s); creating per-test would explode CI time.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark() -> Generator[SparkSession, None, None]:
    """SparkSession scoped to the full test session."""
    session = (
        SparkSession.builder.master("local[2]")
        .appName("pytest")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def sample_reviews_csv(tmp_path: Path) -> Path:
    """Tiny CSV mimicking the IMDB schema, for fast unit tests."""
    csv_path = tmp_path / "dataset.csv"
    csv_path.write_text(
        "review,sentiment\n"
        '"A truly wonderful film. Best of the year.",positive\n'
        '"Boring and predictable. Wasted two hours.",negative\n'
        '"Stellar acting, weak script. Mixed feelings.",positive\n'
        '"<br/>Some HTML embedded</br> and weird symbols !!!.",negative\n'
        '"Plain great. Loved it.",positive\n',
        encoding="utf-8",
    )
    return csv_path
