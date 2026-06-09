# ─── MAKEFILE - COMMON PROJECT COMMANDS ───────────────────────────────────────
#
# A Makefile gives every contributor (and future-you) a single discoverable
# entry point: `make help` lists everything. Convention in most mature Data
# Engineering repos.

.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck lang-check test ci pre-commit \
        ingest package deploy bootstrap data-platform destroy iac-fmt \
        iac-validate iac-security clean docker-build docker-up docker-down

# Variables configurable via environment or command line
PYTHON ?= python3
UV ?= uv
TF ?= terraform
DOCKER_COMPOSE ?= docker compose

INFRA_BOOTSTRAP_DIR := infra/bootstrap
INFRA_PLATFORM_DIR := infra/data-platform

# ─── HELP ─────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── PYTHON ENVIRONMENT ───────────────────────────────────────────────────────
install: ## Install Python dependencies via uv (recommended)
	$(UV) sync --all-extras
	$(UV) run pre-commit install

install-pip: ## Fallback install via pip (no uv available)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	pre-commit install

# ─── CODE QUALITY ─────────────────────────────────────────────────────────────
lint: ## Run ruff linter (check only, no fixes)
	$(UV) run ruff check src/ tests/ scripts/

format: ## Auto-format with ruff
	$(UV) run ruff format src/ tests/ scripts/
	$(UV) run ruff check --fix src/ tests/ scripts/

typecheck: ## Run mypy in strict mode
	$(UV) run mypy src/ scripts/

lang-check: ## Verify no PT-BR leaks in repo-public files
	$(UV) run python scripts/check_no_pt_br.py

test: ## Run pytest with coverage
	$(UV) run pytest -v

test-fast: ## Run only fast tests (skip slow/integration)
	$(UV) run pytest -v -m "not slow and not integration"

pre-commit: ## Run all pre-commit hooks on all files
	$(UV) run pre-commit run --all-files

ci: lint typecheck lang-check test iac-fmt iac-validate ## Run the full CI suite locally

# ─── PIPELINE PACKAGING ───────────────────────────────────────────────────────
package: ## Build pipeline.zip for spark-submit --py-files
	@rm -f build/pipeline.zip
	@mkdir -p build
	cd src && zip -r ../build/pipeline.zip pipeline/ -x '*.pyc' '*__pycache__*'
	@echo "Built build/pipeline.zip ($$(wc -c < build/pipeline.zip) bytes)"

# ─── DATA ─────────────────────────────────────────────────────────────────────
ingest: ## Download the dataset (idempotent)
	$(UV) run python scripts/ingest_data.py

ingest-force: ## Force re-download of the dataset
	$(UV) run python scripts/ingest_data.py --force

# ─── INFRASTRUCTURE ───────────────────────────────────────────────────────────
iac-fmt: ## Run terraform fmt on all Terraform files
	$(TF) fmt -recursive infra/

iac-validate: ## Validate Terraform syntax
	cd $(INFRA_BOOTSTRAP_DIR) && $(TF) init -backend=false && $(TF) validate
	cd $(INFRA_PLATFORM_DIR) && $(TF) init -backend=false && $(TF) validate

iac-security: ## Run Trivy IaC security scan
	trivy config infra/

bootstrap: ## Apply the bootstrap stack (creates remote state bucket)
	cd $(INFRA_BOOTSTRAP_DIR) && $(TF) init
	cd $(INFRA_BOOTSTRAP_DIR) && $(TF) plan -out=tfplan
	cd $(INFRA_BOOTSTRAP_DIR) && $(TF) apply tfplan
	@rm -f $(INFRA_BOOTSTRAP_DIR)/tfplan

data-platform: ## Apply the data-platform stack (runs the EMR cluster)
	cd $(INFRA_PLATFORM_DIR) && $(TF) init -backend-config=scripts/backend.conf
	cd $(INFRA_PLATFORM_DIR) && $(TF) plan -out=tfplan
	cd $(INFRA_PLATFORM_DIR) && $(TF) apply tfplan
	@rm -f $(INFRA_PLATFORM_DIR)/tfplan

deploy: ingest package bootstrap data-platform ## Full deploy: ingest data + package code + bootstrap + data-platform

destroy: ## Destroy ALL resources (data-platform then bootstrap)
	@echo "WARNING: this will destroy ALL provisioned resources."
	@read -p "Type 'destroy' to confirm: " confirm && [ "$$confirm" = "destroy" ] || (echo "Aborted." && exit 1)
	cd $(INFRA_PLATFORM_DIR) && $(TF) destroy -auto-approve || true
	cd $(INFRA_BOOTSTRAP_DIR) && $(TF) destroy -auto-approve || true

# ─── DOCKER ───────────────────────────────────────────────────────────────────
docker-build: ## Build the dev container image
	$(DOCKER_COMPOSE) build

docker-up: ## Start the dev container in background
	$(DOCKER_COMPOSE) up -d

docker-shell: ## Open a shell in the dev container
	$(DOCKER_COMPOSE) exec mz-p2 bash

docker-down: ## Stop and remove the dev container
	$(DOCKER_COMPOSE) down

# ─── MAINTENANCE ──────────────────────────────────────────────────────────────
clean: ## Remove caches and build artifacts (keeps data/ and logs/)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml
	rm -rf build/ dist/ htmlcov/

clean-tf: ## Remove Terraform local state and plan files
	find infra/ -type d -name ".terraform" -exec rm -rf {} + 2>/dev/null || true
	find infra/ -name "tfplan" -delete
	find infra/ -name "*.tfstate*" -delete
