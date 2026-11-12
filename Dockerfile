FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY dbt ./dbt
COPY dashboard ./dashboard
COPY scripts ./scripts
COPY basket.demo.yml ./

ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data \
    TMPDIR=/app/data/tmp \
    DUCKDB_TEMP_DIR=/app/data/duckdb_tmp \
    CANASTA_DATA_DIR=/app/data/raw \
    CANASTA_DB=/app/data/canasta.duckdb \
    DBT_PROFILES_DIR=/app/dbt

EXPOSE 8501
CMD ["./scripts/demo.sh"]
