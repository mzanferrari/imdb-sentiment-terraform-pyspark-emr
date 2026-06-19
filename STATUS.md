# Project Status

Living document tracking the project's evolution. Updated with each meaningful commit.

---

## Current phase: **H1 - Foundations**

Hardening the original course-derived project into a production-grade portfolio piece. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full plan.

Phase mapping: H1 = ROADMAP Phase 1; H2 = Phases 2-3; H3 = Phase 4.

---

## Recent milestones

- `2026-06-10` - **Pre-publication audit pass**: fixed ingestion SHA256 gate, EMR `pipeline.zip` import crash, Terraform state key/lock path and backend single-sourcing; aligned Terraform version to 1.15.5 across CI/docs; deduplicated Dockerfile stage and added OS security upgrade; translated residual PT-BR and renamed the raw-data S3 prefix to `data/`; reconciled README, DEPLOYMENT, ADRs, ROADMAP, ARCHITECTURE with the code on disk.
- `2026-06-09` - **Phase 1 close - containerized dev environment**: multi-stage Dockerfile (Python 3.11, Java 17, Terraform 1.15.5, tflint 0.63.1, AWS CLI, jq, uv 0.11.19, checkov), docker-compose with isolated venv volume, devcontainer with postCreate. Full test suite passes inside the container (pytest + Spark). Terraform `required_version` pinned to `~> 1.15` across all modules; submodule lock files removed from tracking.
- `2026-06-05` - **Audit V3-V5 + Phase 0/1 execution**: fixed the `pipeline.zip` upload gap (build artifact never reached EMR); IAM least-privilege policy; EMR Python 3.11 bootstrap; FinOps guardrails in Terraform (budget + idle alarm); `ml.py` and `s3_io.py` unit tests (coverage ~48%); local environment hardening (numpy, Python pin, Java, ruff bump). Internal audit docs gitignored via glob.
- `2026-05-20` - **Audit V2 hardening pass**: 4 runtime-breaking bugs corrected (EMR step syntax, missing pipeline.zip, LoggerAdapter sentinel capture, PT-BR SSM parameter name); 12 high-severity issues resolved (project_name decoupled from bucket parsing, CrossValidatorModel type, explicit CSV schema, etc.); language-hygiene hook added; `tfsec` migrated to `trivy`/`checkov`.
- `2026-05-19` - **Initial audit & refactor pass**: secrets removed from versioned files, Python code refactored with type hints + structured logging, IaC modularized, CI added, ADRs documented.

---

## H1 - Foundations checklist

### Security & repository hygiene

- [x] Remove versioned `terraform.tfvars` and Account ID
- [x] Add `terraform.tfvars.example` templates
- [x] Remove hardcoded personal email from `Dockerfile`
- [x] Replace `LEIA-ME.txt` with professional `README.md`
- [x] Add `.gitignore` covering Python/Terraform/Docker/IDEs/data
- [x] Add `LICENSE` (MIT)
- [x] Configure `.pre-commit-config.yaml` with `gitleaks`, `ruff`, `mypy`, `terraform_fmt`, `tflint`, `trivy`

### Python code quality

- [x] Fix `path_output` NameError in `ml.py` (was guaranteed runtime failure)
- [x] Remove all `subprocess.run("pip install ...")` from runtime code
- [x] Replace bare `except:` with explicit exception types
- [x] Replace wildcard imports with explicit symbol imports
- [x] Standardize indentation via `ruff format`
- [x] Add type hints and docstrings on all public functions
- [x] Remove `global` mutable state from ML training functions
- [x] Replace `Mtype in("LogisticRegression")` substring test with `==` equality
- [x] Switch ambient-environment detection from filesystem heuristic to `EXECUTION_ENV` env var
- [x] Remove duplicate EMR step that called `main.py` without bucket argument

### Infrastructure

- [x] Switch default region to `eu-west-1` (Ireland)
- [x] Right-size cluster: master `m7g.xlarge`, cores `m7g.xlarge` Spot Graviton
- [x] Add `auto_termination_policy { idle_timeout = 600 }`
- [x] Apply `common_tags` to all resources
- [x] Parametrize `force_destroy` (default `false`)
- [x] Harden `block_public_policy = true` with explicit bucket policy for EMR

### Documentation

- [x] Professional `README.md` with Mermaid architecture diagram
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/DEPLOYMENT.md`
- [x] 8 ADRs (`0001`-`0008`)
- [x] `docs/ROADMAP.md` (phased plan)

### Automation & CI

- [x] `pyproject.toml` + `requirements.txt`
- [x] `Makefile` with discoverable commands
- [x] `scripts/ingest_data.py` (automated, idempotent dataset download)
- [x] `.github/workflows/ci.yml` (lint, type check, tests, IaC validate, security)
- [x] `.github/workflows/security.yml` (scheduled scans)
- [x] Declare `numpy` explicitly (implicit `pyspark.ml` dependency, was missing)
- [x] Pin `requires-python = ">=3.11,<3.12"` (PySpark 3.5 needs `distutils`, removed in 3.12)
- [x] Bump `ruff` to 0.15.x in pre-commit and `pyproject` (align local + hook versions)
- [x] Add `types-tqdm` stub for mypy; enable markdownlint autofix

### Local environment

- [x] Document Java 17 (JRE) as a local prerequisite (PySpark needs a JVM)
- [x] Filter PySpark's socket `ResourceWarning` in pytest (known teardown artifact)
- [x] Devcontainer with Python 3.11 + Java 17 + tooling for dev/prod parity

### Tests

- [x] `tests/conftest.py` with shared SparkSession + sample fixtures
- [x] `tests/test_processing.py` - schema validation, null counts, text cleaning
- [x] `tests/test_config.py` - bucket-name parsing
- [x] `tests/test_ingest.py` - SHA256 + idempotency
- [x] `tests/test_ml.py` - training guard, TrainResult, train_all orchestration; real CV training behind `@pytest.mark.slow`
- [x] `tests/test_s3_io.py` - `_build_path` pure function + local no-op write guards
- [x] Coverage gate at 40% (`--cov-fail-under`), currently ~48%

### FinOps

- [x] EMR sizing documented in `docs/adrs/0003-emr-deployment-mode.md`
- [x] AWS Budget alarm + idle-cluster CloudWatch alarm via Terraform (`modules/finops` + IsIdle alarm in `modules/emr`)

---

## Next phase: **H2 - Differentiation**

Planned start once H1 is complete and the repo has been live for 1-2 weeks of stabilization.

Major scope:

- Domain shift to international trade data (UN Comtrade API)
- Migration to EMR Serverless
- Adoption of dbt for the curated layer
- Apache Iceberg as table format

---

## How to read this file

Recruiters and collaborators: this is the **live** view. The `[x]` and `[ ]` reflect real state, not aspirations. If something is unchecked, it is not done. If something is checked, it has been merged to `main`.
