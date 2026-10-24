# Makefile for imprenta development tasks.
# Dependency resolution and environment management use uv (https://docs.astral.sh/uv/).

.DEFAULT_GOAL := help

UV ?= uv
SRC := src
TESTS := tests

.PHONY: help install sync lock test cov lint fmt fmt-check check docs docs-serve clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install the project with the dev tooling and the TUI
	$(UV) sync --extra dev

sync: install ## Alias for install

lock: ## Resolve and write uv.lock
	$(UV) lock

test: ## Run the test suite
	$(UV) run pytest -q

cov: ## Run the tests with coverage
	$(UV) run pytest --cov=imprenta --cov-report=term-missing

lint: ## Lint with ruff
	$(UV) run ruff check $(SRC) $(TESTS)

fmt: ## Format with ruff
	$(UV) run ruff format $(SRC) $(TESTS)

fmt-check: ## Check formatting
	$(UV) run ruff format --check $(SRC) $(TESTS)

check: lint fmt-check test ## Lint, format check and tests (what CI runs)

# The env vars silence plugin and theme notices about a future MkDocs 2.
docs: ## Build the documentation site into site/ (strict: warnings fail)
	DISABLE_MKDOCS_2_WARNING=true NO_MKDOCS_2_WARNING=1 $(UV) run --group docs mkdocs build --strict

docs-serve: ## Serve the documentation locally with live reload
	DISABLE_MKDOCS_2_WARNING=true NO_MKDOCS_2_WARNING=1 $(UV) run --group docs mkdocs serve

clean: ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache dist build .coverage site
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
