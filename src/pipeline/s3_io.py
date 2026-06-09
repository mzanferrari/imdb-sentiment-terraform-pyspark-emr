"""S3 I/O helpers for the pipeline.

Both write functions are idempotent: existing artifacts at the target prefix are
overwritten cleanly. Spark's `mode("overwrite")` handles atomicity on its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipeline.logging_setup import get_logger

if TYPE_CHECKING:
    from pyspark.ml.base import Model
    from pyspark.ml.tuning import CrossValidatorModel
    from pyspark.sql import DataFrame

    from pipeline.config import PipelineConfig

log = get_logger(__name__)


def _build_path(prefix: str, name: str, *, is_emr: bool, local_fallback: str) -> str:
    """Join prefix+name on EMR, or local_fallback+name when running locally."""
    return f"{prefix}{name}" if is_emr else f"{local_fallback}{name}"


def write_features_to_s3(
    df: DataFrame,
    artifact_name: str,
    config: PipelineConfig,
) -> None:
    """Persist a featurized DataFrame as Parquet partitioned by `label`.

    No-op on local runs (config.is_emr=False) - features stay in memory for
    inspection, with a warning logged so the skip is visible. The DataFrame
    must carry a `label` column for partitioning.
    """
    if not config.is_emr:
        log.warning(
            "skipping feature write (local execution)",
            extra={"artifact": artifact_name},
        )
        return

    target_path = _build_path(
        prefix=config.path_raw_data,
        name=artifact_name,
        is_emr=True,
        local_fallback="data/",
    )

    log.info(
        "writing features",
        extra={"artifact": artifact_name, "path": target_path, "partition_by": "label"},
    )
    df.write.mode("overwrite").partitionBy("label").parquet(target_path)


def write_model_to_s3(
    model: Model | CrossValidatorModel,
    model_label: str,
    config: PipelineConfig,
) -> None:
    """Persist a trained Spark ML model under the output prefix.

    No-op on local runs (same rationale as write_features_to_s3). model_label
    becomes the folder name, e.g. 'LogisticRegression_HTFfeaturizedData'.
    """
    if not config.is_emr:
        log.warning(
            "skipping model write (local execution)",
            extra={"model_label": model_label},
        )
        return

    target_path = _build_path(
        prefix=config.path_output,
        name=model_label,
        is_emr=True,
        local_fallback="output/",
    )

    log.info("writing model", extra={"model_label": model_label, "path": target_path})
    model.write().overwrite().save(target_path)
