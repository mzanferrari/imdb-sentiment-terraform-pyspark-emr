"""Unit tests for s3_io.py helpers.

Strategy:
- _build_path is a pure function (strings + bool in, string out). Both branches
  are tested directly - no Spark, no AWS, instant.
- The write_* functions are tested only on their LOCAL no-op branch
  (is_emr=False): they must log and return without touching S3. We pass a real
  (tiny) DataFrame so the signature is honoured, but no write happens. The EMR
  branch (actual S3 write) is not unit-tested here - it needs a live bucket and
  belongs to an integration test, not a unit test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipeline.config import PipelineConfig
from pipeline.s3_io import _build_path, write_features_to_s3, write_model_to_s3

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def _local_config() -> PipelineConfig:
    return PipelineConfig(
        bucket_name="test-bucket",
        project_name="test-project",
        region="eu-west-1",
        path_raw_data="s3://test-bucket/data/",
        path_output="s3://test-bucket/output/",
        path_logs="s3://test-bucket/logs/",
        is_emr=False,
    )


# ─── _BUILD_PATH (PURE) ───────────────────────────────────────────────────────


def test_build_path_uses_prefix_on_emr() -> None:
    """On EMR, prefix and name are concatenated."""
    result = _build_path(
        prefix="s3://bucket/output/",
        name="model_x",
        is_emr=True,
        local_fallback="output/",
    )
    assert result == "s3://bucket/output/model_x"


def test_build_path_uses_fallback_locally() -> None:
    """Locally, the local_fallback replaces the prefix."""
    result = _build_path(
        prefix="s3://bucket/output/",
        name="model_x",
        is_emr=False,
        local_fallback="output/",
    )
    assert result == "output/model_x"


# ─── WRITE FUNCTIONS - LOCAL NO-OP BRANCH ─────────────────────────────────────


def test_write_features_is_noop_locally(spark: SparkSession) -> None:
    """write_features_to_s3 returns without writing when is_emr=False."""
    df = spark.createDataFrame([(1, 0)], ["value", "label"])
    assert write_features_to_s3(df, "HTFfeaturizedData", _local_config()) is None


def test_write_model_is_noop_locally() -> None:
    """write_model_to_s3 returns without writing when is_emr=False.

    No model object is needed: the local branch returns before touching it,
    so None is a safe stand-in that proves the guard fires first.
    """
    assert write_model_to_s3(None, "LogisticRegression_HTF", _local_config()) is None  # type: ignore[arg-type]
