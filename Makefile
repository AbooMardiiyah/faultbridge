.PHONY: install test lint format run demo

install:
	uv sync

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests

run:
	uv run uvicorn faultbridge.api:app --reload --port 8000

demo:
	PYTHONPATH=src python3 scripts/run_demo.py
