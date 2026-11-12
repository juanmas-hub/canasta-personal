# Canasta personal

[![CI](https://github.com/juanmas-hub/canasta-personal/actions/workflows/ci.yml/badge.svg)](https://github.com/juanmas-hub/canasta-personal/actions/workflows/ci.yml)

Personal grocery-basket index built from Argentina's open SEPA price data
(Secretaría de Comercio, `datos.produccion.gob.ar`).

**Resumen en español (3 líneas):** Toma la base pública diaria de precios SEPA, normaliza
los CSV y modela el costo de una canasta propia de ~20-50 productos. Calcula un índice base
100, el ranking de cadenas y el ahorro potencial. El dashboard Streamlit lee solo marts
livianos; la ingesta y dbt corren con Dagster.

## What it does

- Downloads the daily SEPA ZIP (~320 MB), validates it and processes it in streaming.
- Keeps only scoped data (`AR-C` CABA + `AR-B` Buenos Aires by default) in Parquet.
- Builds two detail levels: aggregates for every EAN and detail only for tracked products
  (basket + top-N EANs).
- Models the data with dbt-duckdb: staging, intermediate and marts.
- Computes a personal basket index (base 100), coverage, carry-forward and a chain ranking.
- Publishes small Parquet marts to the orphan `data` branch for the public dashboard.
- The dashboard lets any visitor build a basket in the browser (catalog search, quantities,
  province), recomputes index and ranking in-session from generic marts, and requires an
  account (Supabase email + password) so the basket persists between visits.

Prices are the values each chain reports to SEPA, not a live shelf price. The index is a
personal basket index, **not** official inflation or INDEC IPC.

## Quickstart

```bash
uv sync
cp .env.example .env          # optional: edit scope, paths and quality thresholds
uv run canasta source         # dates currently published (last 7 days)
uv run canasta ingest --date 2026-11-03
make dbt                      # dbt build over the ingested partition
make marts                    # index, ranking, detail and health Parquet
make demo                     # Streamlit dashboard at localhost:8501 (needs Supabase secrets)
make publish-data             # force-push marts to the orphan `data` branch
```

The dashboard requires accounts: copy `.streamlit/secrets.example.toml` to
`.streamlit/secrets.toml` locally (or set `SUPABASE_URL`/`SUPABASE_ANON_KEY` in the Streamlit
Cloud secrets). See `supabase/schema.sql` and `BLOCKERS.md`.

Docker demo with fixture data (no SEPA download):

```bash
make up                       # docker compose up --build (set SUPABASE_* in .env to log in)
# dashboard: http://localhost:8501
make down
```

Optional local hooks:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Run the pipeline through Dagster:

```bash
make run
```

Materialize a single partition from the CLI:

```bash
uv run dagster asset materialize -m canasta.definitions \
  --select marts/fct_precio_diario --partition 2026-11-03
```

## Layout

```
src/canasta/       ingest, source client, basket, index, ranking, marts, Dagster defs
dbt/               staging, intermediate and marts models + tests
dashboard/         Streamlit app (reads only marts)
scripts/           fixtures and data-branch publisher
tests/             unit tests and dbt fixtures
docs/              sources, decisions, architecture, data model, limitations
```

## Data source and license

Source: Secretaría de Comercio, Precios SEPA (`datos.produccion.gob.ar`), CC BY 4.0.
The CKAN metadata and the `preciosclaros.gob.ar` terms disagree (CC BY 4.0 vs CC BY 2.5 AR);
see `docs/SOURCES.md`. The source only keeps the last seven daily ZIPs, so the history grows
from the moment the pipeline runs.

## Measured numbers (2026-11-03)

| Metric | Value |
|---|---|
| ZIP / CSV | 319,893,305 bytes / 1.533 GB uncompressed |
| Raw products | 14,381,167 |
| Scoped products | 8,965,124 |
| `fct_precio_diario` | 3,335,869 rows |
| `agg_precio_ean_diario` | 122,444 rows |
| Ingest time / peak RSS | 212 s / ~3.97 GB |
| dbt build | 33 nodes, 2.6 s |
| Basket index | 100.00 (first date, 100% coverage) |
| Best chain / saving | Maxi ARS 141,888 / ARS 20,061 |

See `docs/PROGRESS.md` for the command behind each number.

The Streamlit app has five views: basket builder, basket, index series, chain ranking/detail,
and data health. It reads only `data/marts/*.parquet`; locally from disk and on Streamlit
Cloud from the `data` branch through `CANASTA_DATA_URL`. Accounts are required: create a
Supabase project, run `supabase/schema.sql` (table + RLS), disable email confirmation, and
set `SUPABASE_URL`/`SUPABASE_ANON_KEY` in `st.secrets` (see
`.streamlit/secrets.example.toml`). Without them the app shows a configuration error and does
not open.

## CI and scheduled runs

`.github/workflows/ci.yml` runs `ruff`, `mypy`, `pytest` and `make dbt-fixtures` on push/PR.
`.github/workflows/daily.yml` runs the ingest, dbt, marts, retention pruning and data-branch
publication daily at 17:30 UTC and on manual dispatch. It caches `data/raw` between runs so
the index history accumulates (retention: 90 days of detail, 365 of aggregates); it needs
`contents: write` and stores no secrets. `.github/workflows/supabase-ping.yml` hits Supabase
weekly so the free tier does not pause (no-op when the repo secrets are absent).

## Limitations

Only the last seven days are downloadable; backfill is not possible. The source ships
malformed CSV rows, empty inner ZIPs and internal EANs; those are normalized or counted as
rejects. The v1 scope is CABA + Buenos Aires province. The UI basket builder offers only the
~2,500 tracked EANs; the pipeline keeps computing marts from the repo's `basket.yml` (the
example basket). Accounts are mandatory, so Supabase must be configured. See
`docs/LIMITATIONS.md`.
