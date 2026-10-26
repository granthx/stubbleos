.PHONY: install lint format typecheck test test-int cov up down migrate revision demo clean

install:        ## install runtime + dev deps (creates uv.lock on first run; commit it)
	uv sync --all-extras

lint:
	uv run ruff check . && uv run ruff format --check .

format:
	uv run ruff check --fix . && uv run ruff format .

typecheck:
	uv run mypy

test:           ## unit tests (no external services)
	uv run pytest

test-int:       ## needs Postgres/PostGIS (make up) and optionally Redis
	uv run pytest -m integration -o addopts="-ra --strict-markers"

cov:
	uv run pytest --cov --cov-report=term-missing

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	uv run alembic upgrade head

revision:       ## usage: make revision m="add thing"
	uv run alembic revision -m "$(m)"

demo:
	@echo "make demo arrives in Phase 7/8 (needs simulator, agents, dashboard). Nothing to run yet."; exit 2

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
