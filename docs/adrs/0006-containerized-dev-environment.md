# ADR 0006 - Containerized Development Environment

- **Status:** Accepted
- **Date:** 2026-06-09
- **Deciders:** mzanferrari

## Context

The project requires a specific toolchain to run: Python 3.11 (not 3.12, which PySpark 3.5 does not support), Java 17 (for the Spark engine), Terraform 1.15, plus lint and security tooling. Setting this up by hand on each machine is slow and error-prone - the same setup pain repeated per environment. A reproducible container fixes the environment as code.

## Decision

A multi-stage Dockerfile based on `python:3.11-slim-bookworm`:

- The slim base provides the correct Python 3.11 without manual installation.
- Java 17, jq, and git come from the Debian package manager.
- Terraform, tflint, and the AWS CLI are downloaded in an isolated build stage so their download tooling never reaches the final image.
- uv manages Python dependencies; checkov is installed as an isolated tool to keep it out of the project venv.
- The container runs as a non-root user.

A `docker-compose.yml` mounts the repo read-write and the host credentials (`.aws`, `.gitconfig`) read-only. A named volume isolates the container's `.venv` from the host's, preventing mutual overwrite. A `.devcontainer`
configuration lets VS Code open the project directly inside the container, installing dependencies via `postCreateCommand`.

## Consequences

- The test suite (including Spark-dependent tests) runs identically on any machine with Docker - real dev/prod parity for the Python runtime.
- Tool versions are pinned and verified against upstream, not memory: pinning an outdated version (for example an older uv with known advisories) is avoided by checking the source before fixing a version.
- The slim base over a from-scratch Ubuntu build trades some learning value for a smaller, simpler image - proportionate to the goal of a reproducible environment rather than a hand-built one.
- The image is dev and IaC only; EMR runs its own AMI in production. This container is not a production artifact.
- OS security patches are applied at build time via `apt-get upgrade`. This trades bit-for-bit determinism (the base tag is mobile) for fresher CVE fixes - an acceptable trade-off for a dev image. Digest-pinning the base is noted as a future option if this image ever becomes a production base.

## Revisit when

The runtime stack changes (new Python or Spark major), or production execution moves off EMR in a way that makes prod parity require a different base.
