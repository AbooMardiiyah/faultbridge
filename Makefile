.PHONY: install db-up db-down migrate test lint format run worker purge docker-up docker-down docker-status docker-logs docker-workers benchmark-install benchmark-install-faster-whisper-cuda benchmark-install-sbpn benchmark-install-omni benchmark-install-omni-cuda benchmark-prepare benchmark-robustness benchmark-sahara-batch benchmark-sahara-retry benchmark-faster-whisper-cuda benchmark-omni-cuda benchmark-score benchmark-verify-asr-evidence benchmark-agent-prepare benchmark-eval-db benchmark-agent-validate benchmark-agent-run benchmark-agent-score benchmark-privacy-prepare benchmark-privacy-score benchmark-route benchmark-tts-prepare benchmark-tts-generate benchmark-tts-batch benchmark-tts-retry benchmark-tts-asr-faster-whisper benchmark-tts-asr-sbpn benchmark-tts-asr-omni benchmark-tts-score benchmark-tts-audit benchmark-verify-tts-evidence

TORCH_BACKEND ?= cpu
ASR_BATCH_SIZE ?= 10
TTS_BATCH_SIZE ?= 10
TTS_GENDERS ?= female male
AGENT_PROVIDER ?= openai
AGENT_MODEL ?= gpt-4.1-mini
AGENT_REPETITIONS ?= 3

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

benchmark-install-faster-whisper-cuda: .venv-benchmark/bin/python
	UV_CACHE_DIR=.uv-cache UV_HTTP_TIMEOUT=300 uv pip install --python .venv-benchmark/bin/python -r eval/requirements-faster-whisper-cuda.txt

.venv-benchmark/bin/python:
	UV_CACHE_DIR=.uv-cache uv venv .venv-benchmark

benchmark-install-sbpn: .venv-sbpn/bin/python
	UV_CACHE_DIR=.uv-cache uv pip install --python .venv-sbpn/bin/python --torch-backend $(TORCH_BACKEND) -r eval/requirements-sbpn.txt

.venv-sbpn/bin/python:
	UV_CACHE_DIR=.uv-cache uv venv --python 3.11 .venv-sbpn

benchmark-install-omni: .venv-omni/bin/python
	UV_CACHE_DIR=.uv-cache uv pip install --python .venv-omni/bin/python --torch-backend $(TORCH_BACKEND) --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/pt2.8.0/$(TORCH_BACKEND) --index-strategy unsafe-best-match -r eval/requirements-omni.txt

benchmark-install-omni-cuda: .venv-omni/bin/python
	UV_CACHE_DIR=.uv-cache UV_HTTP_TIMEOUT=300 uv pip install --python .venv-omni/bin/python --torch-backend cu128 --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/pt2.8.0/cu128 --index-strategy unsafe-best-match -r eval/requirements-omni-cuda.txt

.venv-omni/bin/python:
	UV_CACHE_DIR=.uv-cache uv venv --python 3.11 .venv-omni

benchmark-prepare:
	VIRTUAL_ENV=.venv-benchmark PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --active --no-sync --env-file .env -m faultbridge_eval.prepare_afriswitch

benchmark-robustness:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.audio_conditions

benchmark-sahara-batch:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.runner --manifest benchmark/manifest.csv --output eval/results/raw --provider sahara-file --limit $(ASR_BATCH_SIZE)

benchmark-sahara-retry:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.runner --manifest benchmark/manifest.csv --output eval/results/raw --provider sahara-file --retry-failures --limit $(ASR_BATCH_SIZE)

benchmark-faster-whisper-cuda:
	CUDA_SITE_PACKAGES="$$(.venv-benchmark/bin/python -c 'import site; print(site.getsitepackages()[0])')"; LD_LIBRARY_PATH="$${CUDA_SITE_PACKAGES}/nvidia/cublas/lib:$${CUDA_SITE_PACKAGES}/nvidia/cudnn/lib" HF_HUB_OFFLINE=1 PYTHONPATH=src:eval .venv-benchmark/bin/python -m faultbridge_eval.runner --manifest benchmark/manifest.csv --output eval/results/raw --provider faster-whisper --whisper-device cuda --whisper-compute-type int8_float16

benchmark-omni-cuda:
	HF_HUB_OFFLINE=1 PYTHONPATH=src:eval .venv-omni/bin/python -m faultbridge_eval.runner --manifest benchmark/manifest.csv --output eval/results/raw --provider omniasr --omni-device cuda

benchmark-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.scorer --manifest benchmark/manifest.csv eval/results/raw/*.jsonl

benchmark-verify-asr-evidence:
	UV_CACHE_DIR=.uv-cache uv run python3 scripts/verify_asr_evidence.py
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.scorer --manifest benchmark/manifest.csv --output /tmp/faultbridge-asr-reproduced.json eval/results/raw/sahara-file-sync.jsonl eval/results/raw/sbpn-base.jsonl eval/results/raw/faster-whisper.jsonl eval/results/raw/meta-omniasr-ctc.jsonl
	cmp benchmark/results/asr_four_model_summary.json /tmp/faultbridge-asr-reproduced.json


benchmark-agent-prepare:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.prepare_agent_scenarios

benchmark-eval-db:
	UV_CACHE_DIR=.uv-cache uv run --env-file .env python3 scripts/create_evaluation_database.py

benchmark-agent-validate:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.validate_agent_scenarios

benchmark-agent-run:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.agent_runner --scenarios benchmark/telco_scenarios.json --agent-provider $(AGENT_PROVIDER) --agent-model $(AGENT_MODEL) --repetitions $(AGENT_REPETITIONS)

benchmark-agent-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.agent_scorer eval/results/agent_runs.jsonl --output benchmark/results/agent_summary.json

benchmark-privacy-prepare:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.prepare_pii_cases

benchmark-privacy-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.privacy_scorer --cases benchmark/pii_cases.jsonl --output benchmark/results/privacy_summary.json

benchmark-route:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.routing_recommender

benchmark-tts-prepare:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_manifest

benchmark-tts-generate:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.tts_runner --transport sync

benchmark-tts-batch:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.tts_runner --transport sync --genders $(TTS_GENDERS) --limit $(TTS_BATCH_SIZE)

benchmark-tts-retry:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run --env-file .env -m faultbridge_eval.tts_runner --transport sync --genders $(TTS_GENDERS) --retry-failures --limit $(TTS_BATCH_SIZE)

benchmark-tts-asr-faster-whisper:
	CUDA_SITE_PACKAGES="$$(.venv-benchmark/bin/python -c 'import site; print(site.getsitepackages()[0])')"; LD_LIBRARY_PATH="$${CUDA_SITE_PACKAGES}/nvidia/cublas/lib:$${CUDA_SITE_PACKAGES}/nvidia/cudnn/lib" HF_HUB_OFFLINE=1 PYTHONPATH=src:eval .venv-benchmark/bin/python -m faultbridge_eval.runner --manifest benchmark/tts_generated.csv --output eval/results/tts/asr --provider faster-whisper --whisper-device cuda --whisper-compute-type int8_float16

benchmark-tts-asr-sbpn:
	PYTHONPATH=src:eval .venv-sbpn/bin/python -m faultbridge_eval.runner --manifest benchmark/tts_generated.csv --output eval/results/tts/asr --provider sbpn

benchmark-tts-asr-omni:
	HF_HUB_OFFLINE=1 PYTHONPATH=src:eval .venv-omni/bin/python -m faultbridge_eval.runner --manifest benchmark/tts_generated.csv --output eval/results/tts/asr --provider omniasr --omni-device cuda

benchmark-tts-score:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_scorer --generation eval/results/tts/sync_generation.jsonl --asr-results eval/results/tts/asr/*.jsonl --public-output benchmark/results/tts_benchmark_summary.json

benchmark-tts-audit:
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_audit --generation eval/results/tts/sync_generation.jsonl

benchmark-verify-tts-evidence:
	UV_CACHE_DIR=.uv-cache uv run python3 scripts/verify_tts_evidence.py
	PYTHONPATH=src:eval UV_CACHE_DIR=.uv-cache uv run -m faultbridge_eval.tts_scorer --generation eval/results/tts/sync_generation.jsonl --asr-results eval/results/tts/asr/*.jsonl --output /tmp/faultbridge-tts-reproduced.json --public-output /tmp/faultbridge-tts-public-reproduced.json
	cmp benchmark/results/tts_benchmark_summary.json /tmp/faultbridge-tts-public-reproduced.json
	cmp benchmark/results/tts_benchmark_summary.csv /tmp/faultbridge-tts-public-reproduced.csv
