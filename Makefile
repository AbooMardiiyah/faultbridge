.PHONY: install db-up db-down migrate test lint format run

install:
	UV_CACHE_DIR=.uv-cache uv sync

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 scripts/migrate.py

test:
	UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 -m unittest discover -s tests -v

lint:
	UV_CACHE_DIR=.uv-cache uv run ruff check src tests
	UV_CACHE_DIR=.uv-cache uv run ruff format --check src tests

format:
	UV_CACHE_DIR=.uv-cache uv run ruff check --fix src tests
	UV_CACHE_DIR=.uv-cache uv run ruff format src tests

run:
	UV_CACHE_DIR=.uv-cache uv run uvicorn faultbridge.api:app --reload --port 8000 --env-file .env
