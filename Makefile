.PHONY: install db-up db-down migrate test lint format run worker purge benchmark-install benchmark-prepare benchmark-robustness benchmark-score benchmark-agent-score benchmark-privacy-score benchmark-route

install:
	UV_CACHE_DIR=.uv-cache uv sync

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 scripts/migrate.py

test:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 -m unittest discover -s tests -v

lint:
	UV_CACHE_DIR=.uv-cache uv run ruff check src tests eval scripts
	UV_CACHE_DIR=.uv-cache uv run ruff format --check src tests eval scripts

format:
	UV_CACHE_DIR=.uv-cache uv run ruff check --fix src tests eval scripts
	UV_CACHE_DIR=.uv-cache uv run ruff format src tests eval scripts

run:
	UV_CACHE_DIR=.uv-cache uv run uvicorn faultbridge.api:app --reload --port 8000 --env-file .env

worker:
	UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 scripts/run_worker.py

purge:
	UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 scripts/purge_expired_calls.py

benchmark-install:
	UV_CACHE_DIR=.uv-cache uv venv .venv-benchmark
	UV_CACHE_DIR=.uv-cache uv pip install --python .venv-benchmark/bin/python -r eval/requirements-benchmark.txt

benchmark-prepare:
	PYTHONPATH=src:eval .venv-benchmark/bin/python -m faultbridge_eval.prepare_afriswitch

benchmark-robustness:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.audio_conditions

benchmark-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.scorer --manifest benchmark/manifest.csv eval/results/raw/*.jsonl

benchmark-agent-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.agent_scorer eval/results/agent_runs.jsonl

benchmark-privacy-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.privacy_scorer --cases benchmark/pii_cases.jsonl

benchmark-route:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.routing_recommender
