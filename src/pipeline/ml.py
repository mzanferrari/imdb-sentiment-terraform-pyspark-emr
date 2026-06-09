"""Model training and evaluation.

Trains a Logistic Regression classifier with cross-validation over each of the
three feature representations produced by `processing.featurize`, and persists
both the trained models and the accuracy scores to S3.

Refactor notes vs the original course code:

- The `path_output` NameError bug is fixed by threading the config through the
  call chain instead of relying on implicit globals.
- Removed `global LR_coefficients` / `global LR_BestModel`. The training function
  now returns a typed result.
- Fixed `Mtype in("LogisticRegression")` (substring test) to `==` (equality test).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.tuning import CrossValidator, CrossValidatorModel, ParamGridBuilder

from pipeline.logging_setup import get_logger
from pipeline.s3_io import write_model_to_s3

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

    from pipeline.config import PipelineConfig

log = get_logger(__name__)

DEFAULT_TRAIN_TEST_SPLIT: tuple[float, float] = (0.7, 0.3)
DEFAULT_SEED: int = 11
DEFAULT_NUM_FOLDS: int = 2
DEFAULT_PARAM_GRID_MAX_ITER: tuple[int, ...] = (10, 15, 20)


@dataclass(frozen=True)
class TrainResult:
    """Outcome of training one classifier on one feature representation."""

    classifier_name: str
    feature_name: str
    accuracy: float


def _train_logistic_regression(train_df: DataFrame) -> CrossValidatorModel:
    """Cross-validate LogisticRegression over the maxIter grid; use `.bestModel`."""
    classifier = LogisticRegression()
    param_grid = (
        ParamGridBuilder().addGrid(classifier.maxIter, list(DEFAULT_PARAM_GRID_MAX_ITER)).build()
    )
    cross_val = CrossValidator(
        estimator=classifier,
        estimatorParamMaps=param_grid,
        evaluator=MulticlassClassificationEvaluator(metricName="accuracy"),
        numFolds=DEFAULT_NUM_FOLDS,
        seed=DEFAULT_SEED,
    )
    return cross_val.fit(train_df)


def train_and_evaluate(
    classifier_name: str,
    feature_df: DataFrame,
    feature_name: str,
    config: PipelineConfig,
) -> TrainResult:
    """Train, evaluate, and persist one classifier over one feature set.

    feature_name labels the output artifact (e.g. 'HTFfeaturizedData'). Raises
    NotImplementedError for any classifier other than 'LogisticRegression'.
    """
    if classifier_name != "LogisticRegression":
        raise NotImplementedError(
            f"Classifier '{classifier_name}' is not implemented. "
            "Only 'LogisticRegression' is currently supported."
        )

    log.info(
        "training",
        extra={"classifier": classifier_name, "features": feature_name},
    )

    train_df, test_df = feature_df.randomSplit(list(DEFAULT_TRAIN_TEST_SPLIT), seed=DEFAULT_SEED)

    fit_model = _train_logistic_regression(train_df)
    predictions = fit_model.transform(test_df)

    evaluator = MulticlassClassificationEvaluator(metricName="accuracy")
    accuracy = float(evaluator.evaluate(predictions)) * 100

    log.info(
        "evaluation complete",
        extra={
            "classifier": classifier_name,
            "features": feature_name,
            "accuracy_pct": round(accuracy, 2),
        },
    )

    # Persist the trained model. config.path_output is explicitly threaded
    # through to write_model_to_s3 - never read from a module global.
    model_label = f"{classifier_name}_{feature_name}"
    write_model_to_s3(fit_model, model_label, config)

    return TrainResult(
        classifier_name=classifier_name,
        feature_name=feature_name,
        accuracy=accuracy,
    )


def train_all(
    htf_df: DataFrame,
    tfidf_df: DataFrame,
    w2v_df: DataFrame,
    config: PipelineConfig,
) -> list[TrainResult]:
    """Train and evaluate LogisticRegression on all three feature sets.

    Returns one TrainResult per representation so the caller can compare
    HashingTF vs TF-IDF vs Word2Vec accuracy.
    """
    feature_sets: list[tuple[str, DataFrame]] = [
        ("HTFfeaturizedData", htf_df),
        ("TFIDFfeaturizedData", tfidf_df),
        ("W2VfeaturizedData", w2v_df),
    ]

    results: list[TrainResult] = []
    for feature_name, df in feature_sets:
        result = train_and_evaluate(
            classifier_name="LogisticRegression",
            feature_df=df,
            feature_name=feature_name,
            config=config,
        )
        results.append(result)

    log.info(
        "all training complete",
        extra={"results": [r.__dict__ for r in results]},
    )
    return results
