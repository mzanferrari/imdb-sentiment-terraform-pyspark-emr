"""Unit tests for pipeline.config.

Covers the PipelineConfig dataclass, SSM parameter fetching (success and the
three error paths that collapse into ConfigError), and load_config wiring
(SSM values plus environment into a PipelineConfig, including the is_emr flag).

Note: the original `_extract_project_name` heuristic (parsing project_name from
bucket_name) was removed; project_name is now a required CLI argument.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from pipeline.config import (
    ConfigError,
    PipelineConfig,
    _fetch_ssm_parameter,
    load_config,
)


class TestPipelineConfig:
    def test_dataclass_is_frozen(self) -> None:
        config = PipelineConfig(
            bucket_name="mz-p2-123456789012",
            project_name="mz-p2",
            region="eu-west-1",
            path_raw_data="s3://mz-p2-123456789012/dados/",
            path_output="s3://mz-p2-123456789012/output/",
            path_logs="s3://mz-p2-123456789012/logs/",
            is_emr=True,
        )
        # Frozen dataclass - mutation should raise
        try:
            config.bucket_name = "other"  # type: ignore[misc]
        except Exception as exc:
            assert "frozen" in str(exc).lower() or "cannot assign" in str(exc).lower()
        else:
            raise AssertionError("Expected frozen dataclass to reject mutation")

    def test_all_fields_required(self) -> None:
        # All seven fields are positional or keyword arguments without defaults
        config = PipelineConfig(
            bucket_name="b",
            project_name="p",
            region="r",
            path_raw_data="d",
            path_output="o",
            path_logs="l",
            is_emr=False,
        )
        assert config.bucket_name == "b"
        assert config.is_emr is False


# ─── _FETCH_SSM_PARAMETER ERROR PATHS ─────────────────────────────────────────


def test_fetch_ssm_raises_on_parameter_not_found() -> None:
    """ParameterNotFound becomes a ConfigError naming the missing parameter."""
    client = MagicMock()
    client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterNotFound"}}, "GetParameter"
    )
    with pytest.raises(ConfigError, match="not found"):
        _fetch_ssm_parameter(client, "test-project", "s3/path_raw_data")


def test_fetch_ssm_raises_on_other_client_error() -> None:
    """A non-NotFound ClientError still becomes ConfigError, with the code."""
    client = MagicMock()
    client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "GetParameter"
    )
    with pytest.raises(ConfigError, match="Failed to read"):
        _fetch_ssm_parameter(client, "test-project", "s3/path_output")


def test_fetch_ssm_raises_on_botocore_error() -> None:
    """A transport-level BotoCoreError becomes ConfigError."""
    client = MagicMock()
    client.get_parameter.side_effect = BotoCoreError()
    with pytest.raises(ConfigError, match="Network/boto error"):
        _fetch_ssm_parameter(client, "test-project", "s3/path_logs")


def test_fetch_ssm_returns_value_on_success() -> None:
    """Happy path returns the parameter value as a string."""
    client = MagicMock()
    client.get_parameter.return_value = {"Parameter": {"Value": "s3://bucket/raw/"}}
    result = _fetch_ssm_parameter(client, "test-project", "s3/path_raw_data")
    assert result == "s3://bucket/raw/"


# ─── LOAD_CONFIG WIRING ───────────────────────────────────────────────────────


@patch("pipeline.config.boto3.client")
def test_load_config_assembles_pipeline_config(mock_boto_client) -> None:
    """load_config wires SSM values and env into a PipelineConfig (EMR mode)."""
    mock_ssm = MagicMock()
    mock_ssm.get_parameter.side_effect = [
        {"Parameter": {"Value": "s3://bucket/raw/"}},
        {"Parameter": {"Value": "s3://bucket/output/"}},
        {"Parameter": {"Value": "s3://bucket/logs/"}},
    ]
    mock_boto_client.return_value = mock_ssm

    with patch.dict("os.environ", {"AWS_DEFAULT_REGION": "eu-west-1", "EXECUTION_ENV": "emr"}):
        config = load_config(bucket_name="test-bucket", project_name="test-project")

    assert config.bucket_name == "test-bucket"
    assert config.project_name == "test-project"
    assert config.region == "eu-west-1"
    assert config.path_raw_data == "s3://bucket/raw/"
    assert config.path_output == "s3://bucket/output/"
    assert config.path_logs == "s3://bucket/logs/"
    assert config.is_emr is True


@patch("pipeline.config.boto3.client")
def test_load_config_sets_is_emr_false_locally(mock_boto_client) -> None:
    """EXECUTION_ENV other than 'emr' yields is_emr=False."""
    mock_ssm = MagicMock()
    mock_ssm.get_parameter.side_effect = [
        {"Parameter": {"Value": "s3://b/raw/"}},
        {"Parameter": {"Value": "s3://b/output/"}},
        {"Parameter": {"Value": "s3://b/logs/"}},
    ]
    mock_boto_client.return_value = mock_ssm

    with patch.dict("os.environ", {"EXECUTION_ENV": "local"}):
        config = load_config(bucket_name="b", project_name="p")

    assert config.is_emr is False
