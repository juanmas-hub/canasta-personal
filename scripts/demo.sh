#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATA_DIR="$ROOT/data"
export TMPDIR="$ROOT/data/tmp"
export DUCKDB_TEMP_DIR="$ROOT/data/duckdb_tmp"
export CANASTA_DATA_DIR="$ROOT/data/raw"
export CANASTA_DB="$ROOT/data/canasta.duckdb"
export DBT_PROFILES_DIR="$ROOT/dbt"
mkdir -p "$TMPDIR" "$DUCKDB_TEMP_DIR" "$CANASTA_DATA_DIR"

uv run python scripts/make_fixtures.py
cp -r tests/fixtures/raw/. "$CANASTA_DATA_DIR"/
[ -f basket.yml ] || cp basket.demo.yml basket.yml
(cd dbt && uv run dbt build --profiles-dir .)
uv run python -m canasta.cli marts --basket basket.yml
exec uv run streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
