# syntax=docker/dockerfile:1.7
#
# Development container for the IMDB sentiment pipeline.
#
# Purpose: standardize Terraform, AWS CLI, and Python versions across all
# developer machines and CI runners. Not used in production (EMR runs its own
# AMI; this image is only for local dev and IaC operations).
#
# Build:  docker compose build
# Run:    docker compose up -d && docker compose exec mz-p2 bash

# ─── STAGE 1 - DOWNLOADS ──────────────────────────────────────────────────────
# Kept separate from the runtime image to avoid leaking download tooling
# into the final layers.
FROM ubuntu:24.04 AS downloads

ARG TERRAFORM_VERSION=1.14.9
ARG AWSCLI_VERSION=2.15.30

# DL3008 = pin apt versions (impractical for base ubuntu); DL3009 = clean apt lists
# hadolint ignore=DL3008,DL3009
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        unzip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /downloads

# Terraform
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
        -o terraform.zip && \
    unzip terraform.zip && \
    rm terraform.zip

# AWS CLI v2
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" \
        -o awscli.zip && \
    unzip awscli.zip && \
    rm awscli.zip

# ─── STAGE 2 - RUNTIME IMAGE ──────────────────────────────────────────────────
FROM ubuntu:24.04

LABEL org.opencontainers.image.title="imdb-sentiment-dev" \
      org.opencontainers.image.description="Development container for the IMDB sentiment pipeline" \
      org.opencontainers.image.source="https://github.com/<your-user>/<repo>" \
      org.opencontainers.image.licenses="MIT"

# Tools needed at runtime - pinned would require apt-mark holds; left unpinned by convention
# hadolint ignore=DL3008,DL3009
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        groff \
        less \
        nano \
        openssh-client \
        python3 \
        python3-pip \
        python3-venv \
        unzip && \
    rm -rf /var/lib/apt/lists/*

# Bring binaries from the download stage
COPY --from=downloads /downloads/terraform /usr/local/bin/terraform
COPY --from=downloads /downloads/aws /opt/aws
RUN /opt/aws/install && rm -rf /opt/aws

# Install uv (modern Python package manager)
RUN pip install --no-cache-dir --break-system-packages uv

# Create a non-root user. Workloads should never run as root by default.
ARG USER_NAME=developer
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid "${USER_GID}" "${USER_NAME}" && \
    useradd --uid "${USER_UID}" --gid "${USER_GID}" --shell /bin/bash --create-home "${USER_NAME}"

USER ${USER_NAME}
WORKDIR /workspace

# Note: git config (user.name, user.email) is intentionally NOT set in the image.
# Mount your ~/.gitconfig from the host or configure inside the container per session.

CMD ["/bin/bash"]
