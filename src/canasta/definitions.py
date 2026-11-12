"""Dagster definitions: ingesta particionada, dbt, checks, schedule y sensor."""

import json
import logging
import os
from collections.abc import Iterator, Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
from dagster import (
    AssetCheckResult,
    AssetExecutionContext,
    AssetSpec,
    DailyPartitionsDefinition,
    DefaultSensorStatus,
    Definitions,
    MaterializeResult,
    RunRequest,
    ScheduleDefinition,
    SkipReason,
    asset,
    asset_check,
    define_asset_job,
    sensor,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from canasta.config import REPO_ROOT, Settings, load_settings
from canasta.ingest import run_ingest
from canasta.source import fetch_resources, resource_for_date

logger = logging.getLogger(__name__)

os.environ.setdefault("CANASTA_DATA_DIR", str(REPO_ROOT / "data" / "raw"))
os.environ.setdefault("CANASTA_DB", str(REPO_ROOT / "data" / "canasta.duckdb"))
os.environ.setdefault("DUCKDB_TEMP_DIR", str(REPO_ROOT / "data" / "duckdb_tmp"))

PARTITIONS = DailyPartitionsDefinition(start_date="2026-10-28")
DBT_DIR = REPO_ROOT / "dbt"

dbt_project = DbtProject(
    project_dir=DBT_DIR,
    profiles_dir=DBT_DIR,
    target="dev",
)
dbt_project.prepare_if_dev()


@asset(partitions_def=PARTITIONS, compute_kind="python")
def sepa_raw_parquet(context: AssetExecutionContext) -> MaterializeResult:
    """Descarga el ZIP del día, lo procesa y escribe Parquet particionado."""
    target_date = date.fromisoformat(context.partition_key)
    result = run_ingest(target_date=target_date, settings=load_settings())
    return MaterializeResult(
        metadata={
            "rows": result.rows,
            "timings": result.timings,
            "source": result.source,
            "peak_rss_kb": result.peak_rss_kb,
        }
    )


class CanastaDbtTranslator(DagsterDbtTranslator):
    def get_asset_spec(
        self, manifest: Mapping[str, Any], unique_id: str, project: DbtProject | None
    ) -> AssetSpec:
        spec = super().get_asset_spec(manifest, unique_id, project)
        return spec.replace_attributes(deps=[sepa_raw_parquet.key])


@dbt_assets(
    manifest=dbt_project.manifest_path,
    partitions_def=PARTITIONS,
    dagster_dbt_translator=CanastaDbtTranslator(),
)
def canasta_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource) -> Iterator[Any]:
    # shortcut: dbt build recorre todas las fechas; con backfill masivo habría que
    # filtrar por var de partición.
    yield from dbt.cli(["build"], context=context).stream()


def _meta(settings: Settings, day: date) -> dict[str, Any]:
    path = settings.raw_dir / "_meta" / f"fecha={day.isoformat()}" / "meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _productos_raw(meta: dict[str, Any]) -> int:
    return int(meta["counts"]["productos_raw"])


def _parquet(settings: Settings, table: str, day: date) -> str:
    return (settings.raw_dir / table / f"fecha={day.isoformat()}" / "part.parquet").as_posix()


@asset_check(asset=sepa_raw_parquet, partitions_def=PARTITIONS, blocking=True)
def check_volumen(context: AssetExecutionContext) -> AssetCheckResult:
    """El volumen del día debe estar dentro de la tolerancia del promedio de 7 días."""
    settings = load_settings()
    day = date.fromisoformat(context.partition_key)
    try:
        current = _productos_raw(_meta(settings, day))
    except (FileNotFoundError, KeyError) as exc:
        return AssetCheckResult(passed=False, metadata={"error": str(exc)})

    previous = []
    for offset in range(1, 8):
        try:
            previous.append(_productos_raw(_meta(settings, day - timedelta(days=offset))))
        except (FileNotFoundError, KeyError):
            continue
    if not previous:
        return AssetCheckResult(
            passed=True,
            metadata={"productos_raw": current, "nota": "sin histórico para comparar"},
        )

    average = sum(previous) / len(previous)
    tolerance = settings.volume_tolerance_pct / 100
    passed = average * (1 - tolerance) <= current <= average * (1 + tolerance)
    return AssetCheckResult(
        passed=passed,
        metadata={
            "productos_raw": current,
            "promedio_7d": average,
            "tolerancia_pct": settings.volume_tolerance_pct,
        },
    )


@asset_check(asset=sepa_raw_parquet, partitions_def=PARTITIONS, blocking=True)
def check_precio(context: AssetExecutionContext) -> AssetCheckResult:
    """Todo precio publicado debe ser positivo; los outliers se reportan."""
    settings = load_settings()
    day = date.fromisoformat(context.partition_key)
    path = _parquet(settings, "fct_precio_diario", day)
    if not Path(path).exists():
        return AssetCheckResult(passed=False, metadata={"error": f"falta {path}"})
    con = duckdb.connect()
    try:
        row = con.execute(
            f"""
            with stats as (
                select ean, provincia, median(precio_lista) as mediana
                from read_parquet('{path}')
                group by 1, 2
            )
            select
                count(*) as n,
                count(*) filter (where p.precio_lista <= 0) as no_positivos,
                count(*) filter (
                    where p.precio_lista > 10 * s.mediana
                       or p.precio_lista < 0.1 * s.mediana
                ) as outliers
            from read_parquet('{path}') p
            join stats s using (ean, provincia)
            """
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    n, no_positivos, outliers = row
    return AssetCheckResult(
        passed=no_positivos == 0,
        metadata={
            "filas": n,
            "precios_no_positivos": no_positivos,
            "outliers": outliers,
            "outliers_pct": (outliers / n * 100) if n else 0,
        },
    )


@asset_check(asset=sepa_raw_parquet, partitions_def=PARTITIONS, blocking=True)
def check_rechazos(context: AssetExecutionContext) -> AssetCheckResult:
    """Los rechazos deben quedar visibles y por debajo del 10% de los productos crudos."""
    settings = load_settings()
    day = date.fromisoformat(context.partition_key)
    rejects_path = _parquet(settings, "rejects", day)
    try:
        total = _productos_raw(_meta(settings, day))
    except (FileNotFoundError, KeyError) as exc:
        return AssetCheckResult(passed=False, metadata={"error": str(exc)})
    if not Path(rejects_path).exists():
        return AssetCheckResult(passed=True, metadata={"rechazos": 0})
    con = duckdb.connect()
    try:
        row = con.execute(
            f"select coalesce(sum(n), 0) from read_parquet('{rejects_path}')"
        ).fetchone()
    finally:
        con.close()
    rejects = int(row[0]) if row else 0
    ratio = rejects / total if total else 0
    return AssetCheckResult(
        passed=ratio < 0.1,
        metadata={"rechazos": rejects, "productos_raw": total, "rechazos_pct": ratio * 100},
    )


daily_job = define_asset_job("daily", selection=[sepa_raw_parquet, canasta_dbt_assets])

daily_schedule = ScheduleDefinition(
    name="daily_sepa",
    job=daily_job,
    cron_schedule="30 16 * * *",
    execution_timezone="UTC",
)

MAX_SOURCE_ATTEMPTS = 8


@sensor(
    job=daily_job,
    minimum_interval_seconds=1800,
    default_status=DefaultSensorStatus.STOPPED,
)
def sepa_source_sensor(context: Any) -> RunRequest | SkipReason:
    """Dispara la partición del día cuando el paquete aparece; reintenta cada 30 min."""
    today = date.today()
    attempts = int(context.cursor or "0")
    try:
        resource_for_date(fetch_resources(), today)
    except Exception as exc:
        attempts += 1
        context.update_cursor(str(attempts))
        if attempts >= MAX_SOURCE_ATTEMPTS:
            logger.error("FALLO_FUENTE fecha=%s intentos=%d error=%s", today, attempts, exc)
        return SkipReason(f"SEPA no publicado ({attempts}/{MAX_SOURCE_ATTEMPTS}): {exc}")
    context.update_cursor("0")
    return RunRequest(partition_key=today.isoformat())


defs = Definitions(
    assets=[sepa_raw_parquet, canasta_dbt_assets],
    asset_checks=[check_volumen, check_precio, check_rechazos],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
    schedules=[daily_schedule],
    sensors=[sepa_source_sensor],
)
