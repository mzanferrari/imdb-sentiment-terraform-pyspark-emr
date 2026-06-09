"""Unit tests for pipeline.processing."""

from __future__ import annotations

from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from pipeline.processing import (
    EXPECTED_COLUMNS,
    EXPECTED_SCHEMA,
    EXPECTED_SENTIMENTS,
    SchemaValidationError,
    calculate_null_counts,
    clean_text_column,
    validate_schema,
)

# ─── CALCULATE_NULL_COUNTS ────────────────────────────────────────────────────


class TestCalculateNullCounts:
    def test_returns_empty_when_no_nulls(self, spark: SparkSession) -> None:
        df = spark.createDataFrame(
            [("good", "positive"), ("bad", "negative")],
            schema=["review", "sentiment"],
        )
        assert calculate_null_counts(df) == []

    def test_detects_nulls_and_computes_percentage(self, spark: SparkSession) -> None:
        df = spark.createDataFrame(
            [("good", "positive"), (None, "negative"), ("ok", None), (None, None)],
            schema="review string, sentiment string",
        )
        result = calculate_null_counts(df)
        result_dict = {col: (count, pct) for col, count, pct in result}

        assert result_dict["review"][0] == 2
        assert result_dict["sentiment"][0] == 2
        assert result_dict["review"][1] == pytest.approx(50.0)
        assert result_dict["sentiment"][1] == pytest.approx(50.0)

    def test_handles_empty_dataframe(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([], schema="review string, sentiment string")
        assert calculate_null_counts(df) == []


# ─── VALIDATE_SCHEMA ──────────────────────────────────────────────────────────


class TestValidateSchema:
    def test_accepts_valid_schema(self, spark: SparkSession) -> None:
        df = spark.createDataFrame(
            [("a", "positive"), ("b", "negative")],
            schema=["review", "sentiment"],
        )
        validate_schema(df)  # Should not raise

    def test_rejects_missing_columns(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([("a",), ("b",)], schema=["review"])
        with pytest.raises(SchemaValidationError, match="missing required columns"):
            validate_schema(df)

    def test_rejects_unexpected_sentiment_values(self, spark: SparkSession) -> None:
        df = spark.createDataFrame(
            [("a", "positive"), ("b", "neutral")],  # 'neutral' is unexpected
            schema=["review", "sentiment"],
        )
        with pytest.raises(SchemaValidationError, match="unexpected values"):
            validate_schema(df)

    def test_expected_constants_are_immutable(self) -> None:
        # Frozensets are hashable and cannot be mutated; protects accidental edits
        assert isinstance(EXPECTED_COLUMNS, frozenset)
        assert isinstance(EXPECTED_SENTIMENTS, frozenset)


# ─── CLEAN_TEXT_COLUMN ────────────────────────────────────────────────────────


class TestCleanTextColumn:
    def test_strips_html_tags(self, spark: SparkSession) -> None:
        df = spark.createDataFrame(
            [("<br/>hello<br/>",)],
            schema=["review"],
        )
        result = clean_text_column(df).collect()[0]["review"]
        assert "<" not in result
        assert ">" not in result
        assert "hello" in result

    def test_removes_digits_and_punctuation(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([("Great movie! 10/10",)], schema=["review"])
        result = clean_text_column(df).collect()[0]["review"]
        assert any(ch.isdigit() for ch in result) is False
        assert "!" not in result
        assert "/" not in result

    def test_lowercases(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([("AMAZING Movie",)], schema=["review"])
        result = clean_text_column(df).collect()[0]["review"]
        assert result == result.lower()

    def test_collapses_multiple_spaces(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([("a    b   c",)], schema=["review"])
        result = clean_text_column(df).collect()[0]["review"]
        assert "  " not in result


# ─── SMOKE TEST ON THE FULL SAMPLE ────────────────────────────────────────────


def test_loading_sample_csv(spark: SparkSession, sample_reviews_csv: Path) -> None:
    """End-to-end light test: loading the sample CSV produces a usable DataFrame.

    Uses the same EXPECTED_SCHEMA enforced in production by `featurize`, so this
    test fails fast if the schema constant drifts away from the actual CSV shape.
    """
    df = spark.read.csv(
        str(sample_reviews_csv),
        header=True,
        escape='"',
        schema=EXPECTED_SCHEMA,
    )

    validate_schema(df)
    assert df.count() == 5
    assert set(df.columns) == {"review", "sentiment"}
