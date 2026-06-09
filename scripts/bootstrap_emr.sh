#!/bin/bash
#
# EMR cluster bootstrap script.
#
# Runs on every node (master + cores) before any step executes.
# Installs the Python dependencies the pipeline needs, into the SAME
# interpreter that Spark uses for PySpark workloads.
#
# Why /usr/bin/python3.11 and not miniconda:
# - EMR 7.13 runs PySpark/Spark workloads on Python 3.11 by default, while the
#   system default python3 (and a naive `pip3 install`) targets Python 3.9.
#   Installing into 3.9 while Spark executes 3.11 yields ModuleNotFoundError
#   for boto3 at runtime. This is a documented 7.12 -> 7.13 change.
#   Ref: AWS EMR 7.13.0 release notes (Python 3.11 default for PySpark).
# - Installing a full Miniconda just to get boto3/botocore is disproportionate
#   (hundreds of MB downloaded on every node) when the runtime Python already
#   exists on the AMI. Use it directly.
#
# Notes:
# - Idempotent: re-running on an existing node is safe (pip is upgrade-safe).
# - Fails fast (set -euo pipefail) so EMR sees a non-zero exit code on error.
# - Only packages the pipeline actually imports are installed (boto3/botocore).
#   structlog was removed: the pipeline uses the stdlib logging module with a
#   custom JsonFormatter (see src/pipeline/logging_setup.py), not structlog.

set -euo pipefail

# Interpreter that Spark uses for PySpark on EMR 7.13. Pinned explicitly so a
# future AMI change surfaces here instead of silently splitting install vs run.
SPARK_PYTHON="/usr/bin/python3.11"

# ─── PYTHON DEPENDENCIES (INTO THE SPARK INTERPRETER) ─────────────────────────
echo "Installing Python dependencies into ${SPARK_PYTHON}"

if [ ! -x "${SPARK_PYTHON}" ]; then
    echo "ERROR: ${SPARK_PYTHON} not found on this AMI. EMR release may have" >&2
    echo "changed the default PySpark interpreter. Aborting bootstrap." >&2
    exit 1
fi

sudo "${SPARK_PYTHON}" -m pip install --upgrade --no-cache-dir pip

sudo "${SPARK_PYTHON}" -m pip install --no-cache-dir \
    "boto3>=1.34,<2.0" \
    "botocore>=1.34,<2.0"

# ─── WORKING DIRECTORIES ──────────────────────────────────────────────────────
mkdir -p "${HOME}/pipeline"
mkdir -p "${HOME}/logs"

echo "Bootstrap complete on $(hostname) using ${SPARK_PYTHON}"
