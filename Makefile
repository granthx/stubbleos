.PHONY: install lint format typecheck test test-int cov up down migrate revision demo results benchmark chaos clean

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

demo:           ## run live demonstration server with full REST API and telemetry
	uv run python -m stubbleos.demo

results:        ## run reproducible evaluation matrix and update results table
	uv run python -m stubbleos.evals.matrix

benchmark:      ## run latency, throughput and scheduler performance benchmarks
	uv run python -m stubbleos.evals.benchmarks

chaos:          ## run adversarial chaos engineering resilience suite
	uv run pytest tests/unit/test_chaos_resilience.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
