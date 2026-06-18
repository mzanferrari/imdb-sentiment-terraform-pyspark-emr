# Roadmap

Planned evolution of the project. Items are grouped by phase and ordered by priority within each phase. Status is reflected in [`../STATUS.md`](../STATUS.md).

---

## Phase 1 - Foundations (current)

Hardening, observability, and documentation.

- [x] Modular Terraform (s3, iam, emr submodules)
- [x] Remote state with native S3 lockfile (Terraform 1.10+)
- [x] Structured JSON logging with correlation ID
- [x] Type hints + docstrings across all Python modules
- [x] Automated dataset ingestion (idempotent, SHA256-verified)
- [x] CI: lint (ruff), type check (mypy), tests (pytest), IaC validate (terraform fmt + tflint + trivy), secret scan (gitleaks)
- [x] Pre-commit hooks for the same suite
- [x] Architecture Decision Records (6 published)
- [x] Right-sized EMR cluster with Spot Graviton core nodes and auto-termination
- [x] EU region as default (`eu-west-1`)
- [x] AWS Budget alarm and idle-cluster CloudWatch alarm via Terraform
- [x] Unit tests for `ml.py` training helpers (CrossValidator setup, model persistence, `TrainResult` shape) - only pipeline module without dedicated coverage
- [x] Containerized dev environment: multi-stage Dockerfile (Python 3.11, Java 17, Terraform 1.15, tooling), docker-compose with isolated venv, devcontainer for VS Code
- [ ] Nightly CI workflow running the slow ML training suite (`pytest -m slow`), separated from PR CI to keep fast feedback
- [ ] Network hardening for EMR: S3 gateway VPC endpoint (zero-cost, keeps S3 traffic in-VPC) and HTTPS-only egress to the internet. Interface endpoints (STS/SSM) deferred on cost grounds for a sporadic, auto-terminating cluster - to be recorded in an ADR

---

## Phase 2 - Domain expansion

Replicate the pipeline pattern against international trade data.

- [ ] Ingestion client for [UN Comtrade API](https://comtradedeveloper.un.org/) with retry, pagination, and rate-limit handling
- [ ] Bronze/silver/gold layering on S3 in Parquet
- [ ] Schema evolution handling (HS classification revisions: HS92, HS96, HS02, HS07, HS12, HS17, HS22)
- [ ] Mirror statistics analysis: reconcile exporter-reported vs. importer-reported flows
- [ ] Slowly Changing Dimension modeling for countries (Sudan/South Sudan split, ex-Yugoslavia, etc.)
- [ ] Notebook reproducing one concrete trade-flow analysis end-to-end
- [ ] ADR documenting the domain shift

---

## Phase 3 - Lakehouse and orchestration

Production-grade patterns.

- [ ] Migration of compute to **EMR Serverless** as default deployment
- [ ] **Apache Iceberg** as table format on S3 (with `dbt-iceberg` for transformations)
- [ ] **dbt Core** for the curated layer with tests and exposures
- [ ] **Apache Polaris** or **Project Nessie** as the Iceberg catalog
- [ ] **Dagster** for orchestration with software-defined assets and lineage
- [ ] **OpenLineage** instrumentation for automated column-level lineage
- [ ] Data quality framework: **Soda Core** integrated in dbt and CI
- [ ] Quality scorecard published monthly per data product
- [ ] **Infracost** running in PRs to flag cost regressions

---

## Phase 4 - Compliance and observability demo

EU-focused capabilities demonstrated against a synthetic PII-bearing dataset.

- [ ] Ingestion-time pseudonymisation with tokenization vault separated from data warehouse
- [ ] Column-level classification (`pii: true`) propagated via Iceberg properties
- [ ] DSAR (right of access) pipeline: given an identifier, return all data about the subject
- [ ] Right to erasure pipeline with audit trail
- [ ] Distributed tracing via OpenTelemetry
- [ ] Spark and dbt metrics exposed to Prometheus
- [ ] CloudWatch Logs Insights dashboards
- [ ] Reusable GitHub Actions workflows across dev/staging/prod with approval gates

---

## Out of scope (deliberately)

- Real-time inference serving - this is a training pipeline, not a model server
- Multi-cloud deployment - the IaC is portable but the project commits to AWS
- Deep-learning models - the classifier choice is intentionally simple; the focus is on the engineering scaffolding
- Multi-tenancy - single-team patterns are sufficient for the scope
