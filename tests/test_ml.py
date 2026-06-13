"""Unit tests for ml.py training helpers.

Test strategy (why it is split this way):

- Fast tests run on every commit/CI: the invalid-classifier guard, the
  TrainResult dataclass, and train_all ORCHESTRATION (does it iterate the
  three feature sets in order and call train_and_evaluate for each), with the
  per-set training mocked so nothing actually trains. Deterministic, sub-second.
- One slow test (marked @pytest.mark.slow) trains a real CrossValidator end to
  end. Excluded from the fast suite (`-m "not slow"`) because a 2-fold CV over
  a maxIter grid costs ~45s and adds flakiness risk; run on demand or nightly.
- The happy path asserts on the CONTRACT (returns TrainResult, accuracy is a
  float in 0-100), never on the accuracy VALUE, which is meaningless on small
  data and would make the test flaky.
- No S3 mock is needed: write_model_to_s3 is a no-op when config.is_emr is
  False, so a local config disables persistence by the code's own design.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pyspark.ml.linalg import Vectors

from pipeline.config import PipelineConfig
from pipeline.ml import TrainResult, train_all, train_and_evaluate

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


# ─── FIXTURES ─────────────────────────────────────────────────────────────────


@pytest.fixture
def local_config() -> PipelineConfig:
    """Config with is_emr=False so model persistence is a no-op."""
    return PipelineConfig(
        bucket_name="test-bucket",
        project_name="test-project",
        region="eu-west-1",
        path_raw_data="s3://test-bucket/data/",
        path_output="s3://test-bucket/output/",
        path_logs="s3://test-bucket/logs/",
        is_emr=False,
    )


@pytest.fixture
def labelled_features(spark: SparkSession):
    """DataFrame with the columns LogisticRegression expects.

    `features` (Vector) and `label` (numeric). Sized so a 70/30 split feeding a
    2-fold CrossValidator leaves data in every fold; a tiny set can empty a
    fold and raise "Nothing has been added to this summarizer". Only used by
    the slow real-training test.
    """

    rows = []
    for i in range(50):
        if i % 2 == 0:
            rows.append((Vectors.dense([0.0 + (i % 5) * 0.02, 1.0]), 0.0))
        else:
            rows.append((Vectors.dense([1.0, 0.0 + (i % 5) * 0.02]), 1.0))
    return spark.createDataFrame(rows, ["features", "label"])


# ─── TRAINRESULT DATACLASS ────────────────────────────────────────────────────


def test_trainresult_holds_fields() -> None:
    """TrainResult stores the three fields it is given."""
    result = TrainResult(
        classifier_name="LogisticRegression",
        feature_name="HTFfeaturizedData",
        accuracy=87.5,
    )
    assert result.classifier_name == "LogisticRegression"
    assert result.feature_name == "HTFfeaturizedData"
    assert result.accuracy == 87.5


def test_trainresult_is_frozen() -> None:
    """TrainResult is immutable (frozen dataclass)."""
    result = TrainResult("LogisticRegression", "HTFfeaturizedData", 87.5)
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError varies
        result.accuracy = 90.0  # type: ignore[misc]


# ─── INVALID CLASSIFIER GUARD ─────────────────────────────────────────────────


def test_train_and_evaluate_rejects_unknown_classifier(
    local_config: PipelineConfig,
) -> None:
    """Any classifier other than LogisticRegression raises NotImplementedError.

    The guard fires before any training, so no DataFrame is needed.
    """
    with pytest.raises(NotImplementedError, match="not implemented"):
        train_and_evaluate(
            classifier_name="RandomForest",
            feature_df=None,  # type: ignore[arg-type]
            feature_name="HTFfeaturizedData",
            config=local_config,
        )


# ─── TRAIN_ALL ORCHESTRATION (MOCKED, FAST) ───────────────────────────────────


def test_train_all_iterates_three_feature_sets(
    local_config: PipelineConfig,
) -> None:
    """train_all calls train_and_evaluate once per representation, in order.

    Per-set training is mocked, so this verifies coordination only: the three
    feature names pass through in the expected order and three results return.
    """
    fake_results = [
        TrainResult("LogisticRegression", "HTFfeaturizedData", 80.0),
        TrainResult("LogisticRegression", "TFIDFfeaturizedData", 82.0),
        TrainResult("LogisticRegression", "W2VfeaturizedData", 78.0),
    ]

    with patch("pipeline.ml.train_and_evaluate", side_effect=fake_results) as mock_te:
        results = train_all(
            htf_df="HTF",  # type: ignore[arg-type]
            tfidf_df="TFIDF",  # type: ignore[arg-type]
            w2v_df="W2V",  # type: ignore[arg-type]
            config=local_config,
        )

    assert len(results) == 3
    assert mock_te.call_count == 3
    passed_feature_names = [c.kwargs["feature_name"] for c in mock_te.call_args_list]
    assert passed_feature_names == [
        "HTFfeaturizedData",
        "TFIDFfeaturizedData",
        "W2VfeaturizedData",
    ]


# ─── HAPPY PATH WITH REAL TRAINING (SLOW, ON DEMAND) ──────────────────────────


@pytest.mark.slow
def test_train_and_evaluate_returns_valid_result(
    labelled_features,
    local_config: PipelineConfig,
) -> None:
    """End-to-end real training returns a well-formed TrainResult.

    Slow (~45s): trains a 2-fold CrossValidator over the maxIter grid. Excluded
    from the fast suite via the `slow` marker. Asserts on contract, not value.
    """
    result = train_and_evaluate(
        classifier_name="LogisticRegression",
        feature_df=labelled_features,
        feature_name="HTFfeaturizedData",
        config=local_config,
    )

    assert isinstance(result, TrainResult)
    assert result.classifier_name == "LogisticRegression"
    assert result.feature_name == "HTFfeaturizedData"
    assert isinstance(result.accuracy, float)
    assert 0.0 <= result.accuracy <= 100.0
