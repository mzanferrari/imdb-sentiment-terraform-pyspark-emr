"""Feature engineering for IMDB sentiment analysis.

Pipeline stages:

1. Load raw CSV from S3 (or local for dev) with explicit schema.
2. Validate schema and report null counts.
3. Audit class balance (positive vs negative).
4. Clean text: strip HTML, non-letter characters, collapse whitespace, lowercase.
5. Tokenize + remove stopwords.
6. Produce three feature representations in parallel:
   - HashingTF (250 features)
   - TF-IDF
   - Word2Vec (vector size 250) + MinMaxScaler

   Word2Vec + MinMaxScaler is preserved from the original course code.
   Semantically it flattens Word2Vec's learned geometry; revisit if model
   performance suffers in production.

All three are returned for downstream classifier comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.ml.feature import (
    IDF,
    HashingTF,
    MinMaxScaler,
    RegexTokenizer,
    StopWordsRemover,
    StringIndexer,
    Word2Vec,
)
from pyspark.sql.functions import col, lower, regexp_replace
from pyspark.sql.types import StringType, StructField, StructType

from pipeline.logging_setup import get_logger
from pipeline.s3_io import write_features_to_s3

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

    from pipeline.config import PipelineConfig

log = get_logger(__name__)

# Schema contract for the input CSV. Reading with this schema fails fast on any
# structural drift rather than silently returning string columns and breaking
# downstream transformations in obscure ways.
EXPECTED_SCHEMA: StructType = StructType(
    [
        StructField("review", StringType(), nullable=False),
        StructField("sentiment", StringType(), nullable=False),
    ]
)
EXPECTED_COLUMNS: frozenset[str] = frozenset({"review", "sentiment"})
EXPECTED_SENTIMENTS: frozenset[str] = frozenset({"positive", "negative"})


class SchemaValidationError(ValueError):
    """Raised when the input DataFrame does not match the expected contract."""


def calculate_null_counts(df: DataFrame) -> list[tuple[str, int, float]]:
    """Return (column, null_count, null_pct) for each column that has nulls.

    Empty list means no nulls anywhere.
    """
    total_rows = df.count()
    if total_rows == 0:
        return []

    result: list[tuple[str, int, float]] = []
    for column_name in df.columns:
        null_count = df.where(col(column_name).isNull()).count()
        if null_count > 0:
            null_pct = (null_count / total_rows) * 100
            result.append((column_name, null_count, null_pct))
    return result


def validate_schema(df: DataFrame) -> None:
    """Check expected columns are present and `sentiment` holds only known labels.

    Raises SchemaValidationError on the first violation found.
    """
    actual_columns = set(df.columns)
    missing = EXPECTED_COLUMNS - actual_columns
    if missing:
        raise SchemaValidationError(
            f"Input CSV is missing required columns: {sorted(missing)}. "
            f"Found: {sorted(actual_columns)}"
        )

    distinct_sentiments = {row["sentiment"] for row in df.select("sentiment").distinct().collect()}
    unexpected = distinct_sentiments - EXPECTED_SENTIMENTS
    if unexpected:
        raise SchemaValidationError(
            f"Column 'sentiment' contains unexpected values: {sorted(unexpected)}. "
            f"Expected only: {sorted(EXPECTED_SENTIMENTS)}"
        )


def clean_text_column(df: DataFrame, source_col: str = "review") -> DataFrame:
    """Strip HTML, drop non-letters, collapse spaces, lowercase `source_col`.

    Order matters: HTML tags are removed before non-letter chars, otherwise
    tag fragments leave isolated letters behind.
    """
    return (
        df.withColumn(source_col, regexp_replace(col(source_col), r"<[^>]*>", ""))
        .withColumn(source_col, regexp_replace(col(source_col), r"[^A-Za-z ]+", ""))
        .withColumn(source_col, regexp_replace(col(source_col), r" +", " "))
        .withColumn(source_col, lower(col(source_col)))
    )


def featurize(
    spark: SparkSession,
    config: PipelineConfig,
) -> tuple[DataFrame, DataFrame, DataFrame]:
    """Load, validate, clean, and featurize the reviews into three representations.

    Returns (HashingTF, TF-IDF, Word2Vec) DataFrames, each carrying at least
    `label`, `features`, `review`, `sentiment`. Raises SchemaValidationError if
    the input CSV breaks the expected schema.
    """
    path = config.path_raw_data if config.is_emr else "data/"

    log.info("loading raw CSV", extra={"path": path})
    reviews = spark.read.csv(
        f"{path}dataset.csv",
        header=True,
        escape='"',
        schema=EXPECTED_SCHEMA,
    )

    log.info("validating schema")
    validate_schema(reviews)

    total = reviews.count()
    log.info("raw rows loaded", extra={"total_rows": total})

    null_columns = calculate_null_counts(reviews)
    if null_columns:
        for column_name, null_count, null_pct in null_columns:
            log.warning(
                "null values detected",
                extra={
                    "column": column_name,
                    "count": null_count,
                    "pct": round(null_pct, 2),
                },
            )
        reviews = reviews.dropna()
        log.info("nulls dropped", extra={"remaining_rows": reviews.count()})
    else:
        log.info("no null values detected")

    pos = reviews.where(col("sentiment") == "positive").count()
    neg = reviews.where(col("sentiment") == "negative").count()
    log.info("class balance", extra={"positive": pos, "negative": neg})

    log.info("indexing labels")
    indexer = StringIndexer(inputCol="sentiment", outputCol="label")
    df_indexed = indexer.fit(reviews).transform(reviews)

    log.info("cleaning text")
    df_cleaned = clean_text_column(df_indexed, source_col="review")

    log.info("tokenizing")
    tokenizer = RegexTokenizer(inputCol="review", outputCol="words", pattern=r"\W")
    df_tokenized = tokenizer.transform(df_cleaned)

    log.info("removing stopwords")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered")
    df_filtered = remover.transform(df_tokenized)

    # ─── HASHINGTF ────────────────────────────────────────────────────────────
    log.info("applying HashingTF")
    hashing_tf = HashingTF(inputCol="filtered", outputCol="rawfeatures", numFeatures=250)
    df_htf = hashing_tf.transform(df_filtered)

    # ─── TF-IDF ───────────────────────────────────────────────────────────────
    log.info("applying TF-IDF")
    idf = IDF(inputCol="rawfeatures", outputCol="features")
    idf_model = idf.fit(df_htf)
    df_tfidf = idf_model.transform(df_htf)

    # Normalize HashingTF column name to match TF-IDF and Word2Vec ("features")
    df_htf = df_htf.withColumnRenamed("rawfeatures", "features")

    # ─── WORD2VEC ─────────────────────────────────────────────────────────────
    log.info("applying Word2Vec + MinMaxScaler")
    w2v = Word2Vec(vectorSize=250, minCount=5, inputCol="filtered", outputCol="features")
    w2v_model = w2v.fit(df_filtered)
    df_w2v_raw = w2v_model.transform(df_filtered)

    scaler = MinMaxScaler(inputCol="features", outputCol="scaledFeatures")
    scaler_model = scaler.fit(df_w2v_raw)
    df_w2v_scaled = scaler_model.transform(df_w2v_raw)

    df_w2v = (
        df_w2v_scaled.drop("features")
        .withColumnRenamed("scaledFeatures", "features")
        .select("sentiment", "review", "label", "features")
    )

    log.info("persisting featurized datasets")
    write_features_to_s3(df_htf, "HTFfeaturizedData", config)
    write_features_to_s3(df_tfidf, "TFIDFfeaturizedData", config)
    write_features_to_s3(df_w2v, "W2VfeaturizedData", config)

    return df_htf, df_tfidf, df_w2v
