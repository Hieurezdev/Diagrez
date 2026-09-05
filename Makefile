UV := uv
PY := $(UV) run python
PRE_COMMIT_CACHE := .pre-commit-cache

.PHONY: setup sync backend frontend build lint format type test check hooks hooks-update clean

setup:
	$(UV) sync --dev
	npm --prefix web install
	PRE_COMMIT_HOME=$(PRE_COMMIT_CACHE) $(UV) run pre-commit install --hook-type pre-commit --hook-type pre-push

sync:
	$(UV) sync --dev

backend:
	$(PY) scripts/dev_backend.py

frontend:
	npm --prefix web run dev

build:
	npm --prefix web run build

lint:
	$(UV) run ruff check core tests scripts main.py
	$(UV) run ruff format --check core tests scripts main.py

format:
	$(UV) run ruff check --fix core tests scripts main.py
	$(UV) run ruff format core tests scripts main.py

type:
	$(UV) run mypy core main.py

test:
	$(UV) run pytest -q

check: lint type test build

hooks:
	PRE_COMMIT_HOME=$(PRE_COMMIT_CACHE) $(UV) run pre-commit run --all-files

hooks-update:
	PRE_COMMIT_HOME=$(PRE_COMMIT_CACHE) $(UV) run pre-commit autoupdate

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache web/dist
