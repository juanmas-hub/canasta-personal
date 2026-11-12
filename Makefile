SHELL := /bin/bash
export TMPDIR := $(CURDIR)/data/tmp
export DATA_DIR := $(CURDIR)/data
export DUCKDB_TEMP_DIR := $(CURDIR)/data/duckdb_tmp
export DBT_PROFILES_DIR := $(CURDIR)/dbt
export CANASTA_DATA_DIR := $(CURDIR)/data/raw
export CANASTA_DB := $(CURDIR)/data/canasta.duckdb

DATE ?= $(shell date +%Y-%m-%d)

.PHONY: setup test lint run up down ingest dbt dbt-fixtures fixtures marts publish-data demo clean

setup:
	mkdir -p data/tmp data/duckdb_tmp
	uv sync
	test -f .env || cp .env.example .env

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src

run:
	uv run dagster dev -m canasta.definitions

ingest:
	uv run python -m canasta.cli ingest --date $(DATE)

dbt:
	cd dbt && uv run dbt build --profiles-dir .

fixtures:
	uv run python scripts/make_fixtures.py

dbt-fixtures: fixtures
	mkdir -p data
	cd dbt && CANASTA_DATA_DIR=../tests/fixtures/raw CANASTA_DB=../data/fixtures.duckdb \
		uv run dbt build --profiles-dir .

marts:
	uv run python -m canasta.cli marts

publish-data: dbt marts
	./scripts/publish_marts.sh

demo: dbt marts
	uv run streamlit run dashboard/app.py

up:
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf data/tmp/* data/duckdb_tmp/* dbt/target dbt/logs .pytest_cache .mypy_cache .ruff_cache
