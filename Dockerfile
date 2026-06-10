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
# hadolint ignore=DL3008,DL3009
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        jq \
        openjdk-17-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Binaries from the download stage
COPY --from=downloads /downloads/terraform /usr/local/bin/terraform
COPY --from=downloads /downloads/tflint /usr/local/bin/tflint
COPY --from=downloads /downloads/aws /tmp/aws-cli/aws
RUN /tmp/aws-cli/aws/install && rm -rf /tmp/aws-cli

# ─── STAGE 2 - RUNTIME IMAGE ──────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="imdb-sentiment-dev" \
      org.opencontainers.image.description="Dev container: PySpark tests, Terraform, lint gate" \
      org.opencontainers.image.licenses="MIT"

# openjdk-17-jre-headless - required by the Spark engine bundled in pyspark
# jq                      - used by the terraform_validate pre-commit hook
# git, ca-certificates    - baseline dev + TLS
# hadolint ignore=DL3008,DL3009
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        jq \
        openjdk-17-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Binaries from the download stage
COPY --from=downloads /downloads/terraform /usr/local/bin/terraform
COPY --from=downloads /downloads/tflint /usr/local/bin/tflint
COPY --from=downloads /downloads/aws /tmp/aws-cli/aws
RUN /tmp/aws-cli/aws/install && rm -rf /tmp/aws-cli

# ─── PYTHON TOOLING - UV AND CHECKOV ──────────────────────────────────────────
# uv: package manager used to install project deps (via devcontainer postCreate).
# checkov: IaC security scan, installed as an isolated tool to keep it out of
# the project venv (lesson from phase 1, where it bloated the venv by ~500MB).
RUN pip install --no-cache-dir uv==0.11.19

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
