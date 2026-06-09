"""Runtime configuration loader.

Single source of truth for paths, region, and bucket. Values come from:

1. Command-line arguments (bucket name + project name - passed by `spark-submit`)
2. SSM Parameter Store under `/${project_name}/...` (S3 paths)
3. Environment variables (region, execution environment override)

Why SSM and not Spark conf or env vars exclusively:

- Spark conf is per-job. SSM is per-project.
- Env vars require Terraform to know the runtime values at provisioning time.
- SSM allows path rotation (e.g., versioned output prefixes) without rerunning Terraform.
- Audit trail of who read what parameter, when (CloudTrail).

Why project_name is a CLI arg instead of being parsed from bucket_name:

- The previous design used `bucket_name.split("-")[0:2]` to derive project_name.
  That breaks for any project whose name itself contains 3+ dash-separated
  tokens. Passing both arguments explicitly removes the coupling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from pipeline.logging_setup import get_logger

if TYPE_CHECKING:
    from mypy_boto3_ssm.client import SSMClient

log = get_logger(__name__)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or unreadable."""


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable runtime configuration, resolved once at pipeline startup.

    The path_* fields are full S3 URI prefixes (raw input, model output, logs).
    is_emr is False for local runs, which skips the S3 writes.
    """

    bucket_name: str
    project_name: str
    region: str
    path_raw_data: str
    path_output: str
    path_logs: str
    is_emr: bool


def _fetch_ssm_parameter(
    client: SSMClient,
    project_name: str,
    param_suffix: str,
) -> str:
    """Read one SSM parameter under the project namespace.

    Wraps boto's ClientError/BotoCoreError into ConfigError so callers get a
    single, meaningful failure type instead of raw boto exceptions.
    """
    name = f"/{project_name}/{param_suffix}"
    try:
        response = client.get_parameter(Name=name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ParameterNotFound":
            raise ConfigError(f"SSM parameter not found: {name}") from exc
        raise ConfigError(f"Failed to read SSM parameter {name}: {error_code}") from exc
    except BotoCoreError as exc:
        raise ConfigError(f"Network/boto error reading SSM parameter {name}") from exc

    return str(response["Parameter"]["Value"])


def load_config(bucket_name: str, project_name: str) -> PipelineConfig:
    """Resolve all pipeline paths from SSM plus the AWS region from the env.

    project_name must match Terraform's var.project_name - it namespaces the
    SSM tree the parameters live under. Raises ConfigError if any required
    parameter is missing.
    """
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")

    log.info(
        "loading configuration",
        extra={"bucket": bucket_name, "project": project_name, "region": region},
    )

    ssm = boto3.client("ssm", region_name=region)

    path_raw_data = _fetch_ssm_parameter(ssm, project_name, "s3/path_raw_data")
    path_output = _fetch_ssm_parameter(ssm, project_name, "s3/path_output")
    path_logs = _fetch_ssm_parameter(ssm, project_name, "s3/path_logs")

    execution_env = os.environ.get("EXECUTION_ENV", "emr").lower()
    is_emr = execution_env == "emr"

    config = PipelineConfig(
        bucket_name=bucket_name,
        project_name=project_name,
        region=region,
        path_raw_data=path_raw_data,
        path_output=path_output,
        path_logs=path_logs,
        is_emr=is_emr,
    )

    log.info("configuration loaded", extra={"config": config.__dict__})
    return config
