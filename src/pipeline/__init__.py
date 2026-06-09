"""IMDB sentiment analysis pipeline - distributed training on Amazon EMR.

This package contains the Spark application code executed inside the EMR cluster.
Configuration (bucket name, S3 paths, region) is read from SSM Parameter Store
at runtime so the same code runs unchanged across dev, staging, and prod accounts.

Entry point: pipeline.main
"""

from importlib.metadata import version

__version__ = version("imdb-sentiment-terraform-pyspark-emr")
