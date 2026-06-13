# syntax=docker/dockerfile:1.7
#
# Development container for the IMDB sentiment pipeline.
#
# A single reproducible environment that runs everything locally: the PySpark
# test suite (Java + Spark via the pyspark wheel), Terraform/AWS operations,
# and the full lint/security gate. Replaces the manual WSL setup. Not used in
# production: EMR runs its own AMI; this image is dev + IaC only.

# ─── STAGE 1 - TOOL DOWNLOADS ─────────────────────────────────────────────────
# Isolated so download tooling (curl, unzip) never reaches the final image.
FROM python:3.11-slim-bookworm AS downloads

ARG TERRAFORM_VERSION=1.15.5
ARG TFLINT_VERSION=0.63.1

# hadolint ignore=DL3008,DL3009
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        unzip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /downloads

# Terraform (pinned; matches the ~> 1.15 constraint in the .tf modules)
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
        -o terraform.zip && \
    unzip terraform.zip && \
    rm terraform.zip

# tflint (pinned; v0.63+ supports Terraform 1.15)
RUN curl -fsSL "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_amd64.zip" \
        -o tflint.zip && \
    unzip tflint.zip && \
    rm tflint.zip

# AWS CLI v2 (official bundled installer; extracts to ./aws with an install script)
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
        -o awscli.zip && \
    unzip -q awscli.zip && \
    rm awscli.zip

# ─── STAGE 2 - RUNTIME IMAGE ──────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="imdb-sentiment-dev" \
      org.opencontainers.image.description="Dev container: PySpark tests, Terraform, lint gate" \
      org.opencontainers.image.licenses="MIT"

# openjdk-17-jre-headless - required by the Spark engine bundled in pyspark
# jq                      - used by the terraform_validate pre-commit hook
# git, ca-certificates    - baseline dev + TLS
#
# apt-get upgrade applies OS security patches over the base image. This trades
# bit-for-bit build determinism (the base tag is mobile) for fresher CVE fixes.
# Acceptable here: this is a dev/IaC image, not a production artifact (ADR-0006).
# apt-get clean + rm lists keeps the layer small.
# hadolint ignore=DL3008,DL3009
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        jq \
        openjdk-17-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Binaries from the download stage
COPY --from=downloads /downloads/terraform /usr/local/bin/terraform
COPY --from=downloads /downloads/tflint /usr/local/bin/tflint
COPY --from=downloads /downloads/aws /tmp/aws-cli/aws
RUN /tmp/aws-cli/aws/install && rm -rf /tmp/aws-cli

# ─── PYTHON TOOLING - UV AND BUILD-TOOL SECURITY PATCHES ──────────────────────
# uv: package manager used to install project deps (via devcontainer postCreate).
# pip/setuptools/wheel are upgraded over the base image to patch known HIGH CVEs:
# - wheel 0.46.2+        CVE-2026-24049 (path traversal in wheel unpack)
# - setuptools 80+       vendors patched jaraco.context 6.1.0 (CVE-2026-23949)
# Versions pinned for reproducibility; bump deliberately when upstream advisories
# require it. terraform/tflint carry a Go stdlib CVE (CVE-2026-42504) fixable
# only by an upstream rebuild; tracked as a maintenance item, not patchable here.
RUN pip install --no-cache-dir \
        "pip==26.1.2" \
        "setuptools==82.0.1" \
        "wheel==0.47.0" \
        "uv==0.11.19"

# ─── NON-ROOT USER ────────────────────────────────────────────────────────────
# Workloads never run as root by default. UID/GID 1000 matches the typical
# host user, avoiding file-ownership friction on the mounted workspace.
ARG USER_NAME=developer
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid "${USER_GID}" "${USER_NAME}" && \
    useradd --uid "${USER_UID}" --gid "${USER_GID}" --shell /bin/bash --create-home "${USER_NAME}"

# Pre-create the venv mount point owned by the non-root user, so the named
# volume mounted at /workspace/.venv inherits writable ownership.
RUN mkdir -p /workspace/.venv && chown "${USER_UID}:${USER_GID}" /workspace/.venv

USER ${USER_NAME}

# checkov installed per-user via uv tool (isolated environment, on PATH).
RUN uv tool install checkov==3.2.533
ENV PATH="/home/${USER_NAME}/.local/bin:${PATH}"

WORKDIR /workspace

# git config (user.name/email) and AWS creds are mounted read-only from the
# host via docker-compose, never baked into the image.

CMD ["/bin/bash"]
