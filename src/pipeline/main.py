"""Pipeline entry point.

Invoked by EMR via:
    spark-submit /home/hadoop/pipeline/main.py <bucket-name> <project-name>

Or locally:
    EXECUTION_ENV=local python -m pipeline.main <bucket-name> <project-name>
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from pipeline.config import ConfigError, load_config
from pipeline.logging_setup import configure_logging, get_logger
from pipeline.ml import train_all
from pipeline.processing import SchemaValidationError, featurize

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

log = get_logger(__name__)


def _build_spark_session(app_name: str = "imdb-sentiment-pipeline") -> SparkSession:
    """Create or get the active SparkSession; raises RuntimeError if it can't init."""
    from pyspark.sql import SparkSession  # noqa: PLC0415 - lazy import to keep --help fast

    try:
        spark = SparkSession.builder.appName(app_name).getOrCreate()
        spark.sparkContext.setLogLevel("ERROR")
        return spark
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize Spark: {exc}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="IMDB sentiment analysis pipeline.")
    parser.add_argument(
        "bucket_name",
        help="S3 bucket name (without s3:// prefix).",
    )
    parser.add_argument(
        "project_name",
        help="Project namespace, matching Terraform var.project_name.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level for the pipeline.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Orchestrate config -> Spark -> featurize -> train.

    Returns 0 on success; distinct non-zero codes per failure stage (2 config,
    3 spark, 4 schema, 5 featurize, 6 train) so the EMR step log pinpoints where
    it broke.
    """
    args = parse_args(argv)

    correlation_id = configure_logging(level=args.log_level)
    log.info(
        "pipeline starting",
        extra={
            "correlation_id": correlation_id,
            "bucket": args.bucket_name,
            "project": args.project_name,
        },
    )

    # Resolve configuration before allocating Spark resources.
    try:
        config = load_config(args.bucket_name, args.project_name)
    except ConfigError:
        log.error("configuration failed", exc_info=True)
        return 2

    # Spark lifecycle wrapped in try/finally to guarantee teardown.
    spark = None
    try:
        spark = _build_spark_session()
    except RuntimeError:
        log.error("spark initialization failed", exc_info=True)
        return 3

    try:
        try:
            htf_df, tfidf_df, w2v_df = featurize(spark, config)
        except SchemaValidationError:
            log.error("schema validation failed", exc_info=True)
            return 4
        except Exception:
            log.error("feature engineering failed", exc_info=True)
            return 5

        try:
            results = train_all(htf_df, tfidf_df, w2v_df, config)
        except Exception:
            log.error("model training failed", exc_info=True)
            return 6

        log.info(
            "pipeline complete",
            extra={
                "results": [
                    {
                        "classifier": r.classifier_name,
                        "features": r.feature_name,
                        "accuracy_pct": round(r.accuracy, 2),
                    }
                    for r in results
                ]
            },
        )
        return 0
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    sys.exit(main())
