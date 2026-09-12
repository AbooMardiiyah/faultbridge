.PHONY: install db-up db-down migrate test lint format run worker purge docker-up docker-down docker-status docker-logs docker-workers benchmark-install benchmark-install-sbpn benchmark-install-omni benchmark-prepare benchmark-robustness benchmark-score benchmark-agent-score benchmark-privacy-score benchmark-route benchmark-tts-prepare benchmark-tts-generate benchmark-tts-asr-faster-whisper benchmark-tts-asr-sbpn benchmark-tts-asr-omni benchmark-tts-score benchmark-tts-audit

TORCH_BACKEND ?= cpu

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

docker-up:
	docker compose up -d --build --wait api

docker-down:
	docker compose down

docker-status:
	docker compose ps

docker-logs:
	docker compose logs --tail=100 -f api postgres

docker-workers:
	docker compose --profile workers up -d --build worker

benchmark-install: .venv-benchmark/bin/python
	UV_CACHE_DIR=.uv-cache uv pip install --python .venv-benchmark/bin/python -r eval/requirements-benchmark.txt

.venv-benchmark/bin/python:
	UV_CACHE_DIR=.uv-cache uv venv .venv-benchmark

benchmark-install-sbpn: .venv-sbpn/bin/python
	UV_CACHE_DIR=.uv-cache uv pip install --python .venv-sbpn/bin/python --torch-backend $(TORCH_BACKEND) -r eval/requirements-sbpn.txt

.venv-sbpn/bin/python:
	UV_CACHE_DIR=.uv-cache uv venv --python 3.11 .venv-sbpn

benchmark-install-omni: .venv-omni/bin/python
	UV_CACHE_DIR=.uv-cache uv pip install --python .venv-omni/bin/python --torch-backend $(TORCH_BACKEND) --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/pt2.8.0/$(TORCH_BACKEND) --index-strategy unsafe-best-match -r eval/requirements-omni.txt

.venv-omni/bin/python:
	UV_CACHE_DIR=.uv-cache uv venv --python 3.11 .venv-omni

benchmark-prepare:
	VIRTUAL_ENV=.venv-benchmark PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --active --no-sync --env-file .env -m faultbridge_eval.prepare_afriswitch

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

benchmark-tts-prepare:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_manifest

benchmark-tts-generate:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.tts_runner

benchmark-tts-asr-faster-whisper:
	PYTHONPATH=src:eval .venv-benchmark/bin/python -m faultbridge_eval.runner --manifest benchmark/tts_generated.csv --output eval/results/tts/asr --provider faster-whisper

benchmark-tts-asr-sbpn:
	PYTHONPATH=src:eval .venv-sbpn/bin/python -m faultbridge_eval.runner --manifest benchmark/tts_generated.csv --output eval/results/tts/asr --provider sbpn

benchmark-tts-asr-omni:
	PYTHONPATH=src:eval .venv-omni/bin/python -m faultbridge_eval.runner --manifest benchmark/tts_generated.csv --output eval/results/tts/asr --provider omniasr

benchmark-tts-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_scorer --generation eval/results/tts/generation.jsonl --asr-results eval/results/tts/asr/*.jsonl

benchmark-tts-audit:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_audit
