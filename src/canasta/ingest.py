"""Idempotent SEPA ingest: outer ZIP -> nested per-store ZIPs -> Parquet partitions."""

from __future__ import annotations

import json
import logging
import os
import resource
import shutil
import time
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import IO, Any

import duckdb

from canasta.basket import Basket, active_basket_path, load_basket
from canasta.config import Settings
from canasta.ean import is_valid_ean
from canasta.source import download_resource, fetch_resources, resource_for_date

logger = logging.getLogger(__name__)

COMERCIO_COLUMNS = [
    "id_comercio",
    "id_bandera",
    "comercio_cuit",
    "comercio_razon_social",
    "comercio_bandera_nombre",
    "comercio_bandera_url",
    "comercio_ultima_actualizacion",
    "comercio_version_sepa",
]

SUCURSALES_COLUMNS = [
    "id_comercio",
    "id_bandera",
    "id_sucursal",
    "sucursales_nombre",
    "sucursales_tipo",
    "sucursales_calle",
    "sucursales_numero",
    "sucursales_latitud",
    "sucursales_longitud",
    "sucursales_observaciones",
    "sucursales_barrio",
    "sucursales_codigo_postal",
    "sucursales_localidad",
    "sucursales_provincia",
    "sucursales_lunes_horario_atencion",
    "sucursales_martes_horario_atencion",
    "sucursales_miercoles_horario_atencion",
    "sucursales_jueves_horario_atencion",
    "sucursales_viernes_horario_atencion",
    "sucursales_sabado_horario_atencion",
    "sucursales_domingo_horario_atencion",
]

PRODUCTOS_COLUMNS = [
    "id_comercio",
    "id_bandera",
    "id_sucursal",
    "id_producto",
    "productos_ean",
    "productos_descripcion",
    "productos_cantidad_presentacion",
    "productos_unidad_medida_presentacion",
    "productos_marca",
    "productos_precio_lista",
    "productos_precio_referencia",
    "productos_cantidad_referencia",
    "productos_unidad_medida_referencia",
    "productos_precio_unitario_promo1",
    "productos_leyenda_promo1",
    "productos_precio_unitario_promo2",
    "productos_leyenda_promo2",
]

EXPECTED = {
    "comercio.csv": COMERCIO_COLUMNS,
    "sucursales.csv": SUCURSALES_COLUMNS,
    "productos.csv": PRODUCTOS_COLUMNS,
}


class SchemaError(RuntimeError):
    """The source changed its columns; stop the run instead of guessing."""


def _as_varchar(columns: Sequence[str]) -> dict[str, str]:
    return {column: "VARCHAR" for column in columns}


def _create_raw_table(con: duckdb.DuckDBPyConnection, table: str, columns: Sequence[str]) -> None:
    con.execute(f"CREATE TABLE {table} ({', '.join(f'{c} VARCHAR' for c in columns)})")


def _is_valid_ean_udf(code: str | None) -> bool:
    return bool(code) and is_valid_ean(str(code))


def _iter_lines(src: IO[bytes]) -> Iterator[bytes]:
    buffer = b""
    while chunk := src.read(1024 * 1024):
        buffer += chunk
        parts = buffer.split(b"\n")
        buffer = parts.pop()
        yield from parts
    if buffer:
        yield buffer


def _write_row(out: IO[bytes], row: bytes, n_fields: int) -> None:
    separators = row.count(b"|")
    if separators > n_fields - 1:
        raise SchemaError(f"too many fields: expected {n_fields}, got {separators + 1}")
    out.write(row + b"|" * (n_fields - 1 - separators) + b"\n")


def _normalize_csv(src: IO[bytes], dest: Path, expected: Sequence[str]) -> None:
    lines = _iter_lines(src)
    first = next(lines, b"")
    if not first:
        raise SchemaError("empty CSV")
    header = first.decode("utf-8-sig").strip("\r")
    fields = [field.strip() for field in header.split("|")]
    if fields != list(expected):
        missing = sorted(set(expected) - set(fields))
        unexpected = sorted(set(fields) - set(expected))
        raise SchemaError(
            f"column mismatch in {dest.name}: missing={missing} unexpected={unexpected}"
        )
    n_fields = len(expected)
    with dest.open("wb") as out:
        out.write(("|".join(fields) + "\n").encode("utf-8"))
        pending = b""
        for raw in lines:
            line = raw.replace(b"\x00", b"")
            if line.endswith(b"\r"):
                line = line[:-1]
            if not line or line.isspace():
                continue
            if b"|" not in line and b"actualizaci" in line.lower():
                break
            if line.startswith(b"|"):
                if not pending:
                    raise SchemaError("continuation line without a row")
                pending += line
            else:
                if pending:
                    _write_row(out, pending, n_fields)
                pending = line
            if pending.count(b"|") >= n_fields - 1:
                _write_row(out, pending, n_fields)
                pending = b""
        if pending:
            _write_row(out, pending, n_fields)


def _iter_inner_zips(outer_path: Path, work_dir: Path) -> Iterator[Path]:
    inner_path = work_dir / "inner.zip"
    with zipfile.ZipFile(outer_path) as outer:
        members = sorted(name for name in outer.namelist() if name.lower().endswith(".zip"))
        if not members:
            raise SchemaError(f"no nested ZIPs found in {outer_path}")
        for member in members:
            if outer.getinfo(member).file_size == 0:
                logger.warning("event=skip_empty_inner member=%s", member)
                continue
            with outer.open(member) as src, inner_path.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            yield inner_path


def _connect(db_path: Path, settings: Settings) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute("SET memory_limit='4GB'")
    con.execute("SET threads=4")
    con.execute(f"SET temp_directory='{settings.duckdb_temp_dir.as_posix()}'")
    con.create_function(
        "is_valid_ean",
        _is_valid_ean_udf,
        ["VARCHAR"],
        "BOOLEAN",
    )
    _create_raw_table(con, "comercios_raw", COMERCIO_COLUMNS)
    _create_raw_table(con, "sucursales_raw", SUCURSALES_COLUMNS)
    _create_raw_table(con, "productos_raw", PRODUCTOS_COLUMNS)
    return con


def _load_inner_zip(con: duckdb.DuckDBPyConnection, inner_path: Path, work_dir: Path) -> None:
    with zipfile.ZipFile(inner_path) as inner:
        members: dict[str, str] = {}
        for name in inner.namelist():
            base = Path(name).name
            if base in EXPECTED:
                if base in members:
                    raise SchemaError(f"duplicate {base} in nested ZIP")
                members[base] = name
        for base, expected in EXPECTED.items():
            if base not in members:
                raise SchemaError(f"missing {base} in nested ZIP")
            normalized = work_dir / f"{base}.norm"
            with inner.open(members[base]) as src:
                _normalize_csv(src, normalized, expected)
            table = {
                "comercio.csv": "comercios_raw",
                "sucursales.csv": "sucursales_raw",
                "productos.csv": "productos_raw",
            }[base]
            relation = con.read_csv(
                str(normalized),
                columns=_as_varchar(expected),
                header=True,
                delimiter="|",
                quotechar='"',
                escapechar='"',
                auto_detect=False,
            )
            relation.insert_into(table)
            normalized.unlink(missing_ok=True)


def _prepare_tables(con: duckdb.DuckDBPyConnection, settings: Settings, basket: Basket) -> None:
    scope = ", ".join(f"'{province}'" for province in settings.scope_provinces)
    con.execute(
        """
        CREATE OR REPLACE TABLE sucursales_dedup AS
        SELECT * EXCLUDE (rn) FROM (
          SELECT *, row_number() OVER (
            PARTITION BY id_comercio, id_bandera, id_sucursal
            ORDER BY sucursales_nombre
          ) AS rn
          FROM sucursales_raw
        ) WHERE rn = 1
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE comercios_dedup AS
        SELECT * EXCLUDE (rn) FROM (
          SELECT *, row_number() OVER (
            PARTITION BY id_comercio, id_bandera
            ORDER BY comercio_bandera_nombre
          ) AS rn
          FROM comercios_raw
        ) WHERE rn = 1
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE productos_base AS
        SELECT
          p.*,
          TRY_CAST(p.productos_ean AS INTEGER) AS ean_num,
          TRY_CAST(p.productos_precio_lista AS DOUBLE) AS precio_num,
          s.sucursales_provincia AS provincia,
          s.sucursales_localidad AS localidad,
          COALESCE(
            NULLIF(TRIM(c.comercio_bandera_nombre), ''),
            NULLIF(TRIM(c.comercio_razon_social), ''),
            p.id_comercio
          ) AS cadena
        FROM productos_raw p
        LEFT JOIN sucursales_dedup s
          USING (id_comercio, id_bandera, id_sucursal)
        LEFT JOIN comercios_dedup c
          USING (id_comercio, id_bandera)
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE ean_check AS
        SELECT DISTINCT id_producto, is_valid_ean(id_producto) AS valid
        FROM productos_base
        WHERE ean_num = 1
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE sucursales_scoped AS
        SELECT * FROM sucursales_dedup
        WHERE UPPER(TRIM(sucursales_provincia)) IN ({scope})
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE comercios_scoped AS
        SELECT DISTINCT c.*
        FROM comercios_dedup c
        WHERE (c.id_comercio, c.id_bandera) IN (
          SELECT id_comercio, id_bandera FROM sucursales_scoped
        )
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE productos_scope AS
        SELECT
          p.id_comercio,
          p.id_bandera,
          p.id_sucursal,
          p.id_producto AS ean,
          p.productos_descripcion AS descripcion,
          p.productos_marca AS marca,
          p.precio_num AS precio_lista,
          TRY_CAST(p.productos_precio_referencia AS DOUBLE) AS precio_referencia,
          TRY_CAST(p.productos_cantidad_referencia AS DOUBLE) AS cantidad_referencia,
          p.productos_unidad_medida_referencia AS unidad_referencia,
          TRY_CAST(p.productos_cantidad_presentacion AS DOUBLE) AS cantidad_presentacion,
          p.productos_unidad_medida_presentacion AS unidad_presentacion,
          TRY_CAST(p.productos_precio_unitario_promo1 AS DOUBLE) AS promo1,
          TRY_CAST(p.productos_precio_unitario_promo2 AS DOUBLE) AS promo2,
          UPPER(TRIM(p.provincia)) AS provincia,
          p.localidad,
          p.cadena
        FROM productos_base p
        JOIN ean_check e USING (id_producto)
        WHERE p.ean_num = 1
          AND e.valid
          AND p.precio_num > 0
          AND UPPER(TRIM(p.provincia)) IN ({scope})
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE productos_dedup AS
        SELECT
          id_comercio, id_bandera, id_sucursal, ean, provincia, localidad, cadena,
          any_value(descripcion) AS descripcion,
          any_value(marca) AS marca,
          median(precio_lista) AS precio_lista,
          any_value(precio_referencia) AS precio_referencia,
          any_value(cantidad_referencia) AS cantidad_referencia,
          any_value(unidad_referencia) AS unidad_referencia,
          any_value(cantidad_presentacion) AS cantidad_presentacion,
          any_value(unidad_presentacion) AS unidad_presentacion,
          any_value(promo1) AS promo1,
          any_value(promo2) AS promo2
        FROM productos_scope
        GROUP BY id_comercio, id_bandera, id_sucursal, ean, provincia, localidad, cadena
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE top_eans AS
        SELECT ean, COUNT(DISTINCT id_sucursal) AS n_sucursales, COUNT(*) AS n_observaciones
        FROM productos_dedup
        GROUP BY ean
        ORDER BY n_sucursales DESC, n_observaciones DESC, ean
        LIMIT ?
        """,
        [settings.top_n_eans],
    )
    con.execute("CREATE OR REPLACE TABLE basket_eans (ean VARCHAR)")
    con.execute(
        "CREATE OR REPLACE TABLE basket_items (ean VARCHAR, label VARCHAR, qty_per_month DOUBLE)"
    )
    if basket.eans:
        con.executemany("INSERT INTO basket_eans VALUES (?)", [(ean,) for ean in basket.eans])
        con.executemany(
            "INSERT INTO basket_items VALUES (?, ?, ?)",
            [(item.ean, item.label, item.qty_per_month) for item in basket.items],
        )
    con.execute(
        """
        CREATE OR REPLACE TABLE tracked_eans AS
        SELECT ean FROM top_eans
        UNION
        SELECT ean FROM basket_eans
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE rejects AS
        SELECT 'ean_interno' AS motivo, COUNT(*) AS n
        FROM productos_base WHERE ean_num = 0
        UNION ALL
        SELECT 'ean_flag_invalido', COUNT(*) FROM productos_base WHERE ean_num IS NULL
        UNION ALL
        SELECT 'ean_invalido', COUNT(*)
        FROM productos_base p
        LEFT JOIN ean_check e USING (id_producto)
        WHERE p.ean_num = 1 AND NOT COALESCE(e.valid, FALSE)
        UNION ALL
        SELECT 'precio_invalido', COUNT(*)
        FROM productos_base
        WHERE ean_num = 1 AND (precio_num IS NULL OR precio_num <= 0)
        UNION ALL
        SELECT 'sucursal_desconocida', COUNT(*)
        FROM productos_base WHERE provincia IS NULL
        """
    )


def _write_parquet(con: duckdb.DuckDBPyConnection, query: str, target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    tmp = target / "part.parquet.tmp"
    final = target / "part.parquet"
    con.execute(f"COPY ({query}) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    os.replace(tmp, final)
    for child in target.iterdir():
        if child != final:
            child.unlink(missing_ok=True)
    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{final.as_posix()}')").fetchone()
    return int(rows[0]) if rows else 0


def _write_single_parquet(con: duckdb.DuckDBPyConnection, query: str, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    con.execute(f"COPY ({query}) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    os.replace(tmp, target)
    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{target.as_posix()}')").fetchone()
    return int(rows[0]) if rows else 0


def _write_outputs(
    con: duckdb.DuckDBPyConnection, settings: Settings, target_date: date
) -> dict[str, int]:
    day = target_date.isoformat()
    rows: dict[str, int] = {}
    base = settings.raw_dir
    rows["agg_precio_ean_diario"] = _write_parquet(
        con,
        f"""
        SELECT
          DATE '{day}' AS fecha,
          ean,
          provincia,
          MIN(precio_lista) AS min,
          quantile_cont(precio_lista, 0.25) AS p25,
          median(precio_lista) AS mediana,
          quantile_cont(precio_lista, 0.75) AS p75,
          MAX(precio_lista) AS max,
          COUNT(DISTINCT id_sucursal) AS n_sucursales,
          COUNT(*) AS n_observaciones
        FROM productos_dedup
        GROUP BY ean, provincia
        ORDER BY ean, provincia
        """,
        base / "agg_precio_ean_diario" / f"fecha={day}",
    )
    rows["fct_precio_diario"] = _write_parquet(
        con,
        f"""
        SELECT
          DATE '{day}' AS fecha,
          id_comercio,
          id_bandera,
          cadena,
          id_sucursal,
          ean,
          descripcion,
          marca,
          precio_lista,
          precio_referencia,
          cantidad_referencia,
          unidad_referencia,
          cantidad_presentacion,
          unidad_presentacion,
          promo1,
          promo2,
          provincia,
          localidad
        FROM productos_dedup
        WHERE ean IN (SELECT ean FROM tracked_eans)
        ORDER BY ean, cadena, id_sucursal
        """,
        base / "fct_precio_diario" / f"fecha={day}",
    )
    rows["sucursales"] = _write_parquet(
        con,
        """
        SELECT * FROM sucursales_scoped
        ORDER BY id_comercio, id_bandera, id_sucursal
        """,
        base / "sucursales" / f"fecha={day}",
    )
    rows["comercios"] = _write_parquet(
        con,
        """
        SELECT * FROM comercios_scoped
        ORDER BY id_comercio, id_bandera
        """,
        base / "comercios" / f"fecha={day}",
    )
    rows["rejects"] = _write_parquet(
        con,
        f"""
        SELECT DATE '{day}' AS fecha, motivo, n
        FROM rejects WHERE n > 0
        ORDER BY motivo
        """,
        base / "rejects" / f"fecha={day}",
    )
    rows["basket_items"] = _write_single_parquet(
        con,
        "SELECT ean, label, qty_per_month FROM basket_items ORDER BY ean",
        base / "basket_items.parquet",
    )
    return rows


def _write_meta(settings: Settings, target_date: date, payload: dict[str, Any]) -> None:
    target = settings.raw_dir / "_meta" / f"fecha={target_date.isoformat()}"
    target.mkdir(parents=True, exist_ok=True)
    final = target / "meta.json"
    tmp = target / "meta.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, final)


@dataclass
class IngestResult:
    fecha: date
    rows: dict[str, int] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    peak_rss_kb: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "fecha": self.fecha.isoformat(),
            "rows": self.rows,
            "timings": self.timings,
            "source": self.source,
            "peak_rss_kb": self.peak_rss_kb,
        }


def run_ingest(
    target_date: date,
    settings: Settings,
    zip_path: Path | None = None,
    keep_temp: bool = False,
) -> IngestResult:
    work_dir = settings.tmp_dir / f"ingest_{target_date.isoformat()}"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = work_dir / "ingest.duckdb"
    result = IngestResult(fecha=target_date)
    started = time.monotonic()
    con: duckdb.DuckDBPyConnection | None = None
    try:
        if zip_path is None:
            resources = fetch_resources()
            sepa_resource = resource_for_date(resources, target_date)
            zip_path = work_dir / "sepa.zip"
            result.source = download_resource(sepa_resource, zip_path)
            result.source["date"] = sepa_resource.date.isoformat()
            result.source["name"] = sepa_resource.name
        else:
            result.source = {"path": str(zip_path), "bytes": zip_path.stat().st_size}
        download_done = time.monotonic()

        con = _connect(db_path, settings)
        loaded = 0
        for inner_path in _iter_inner_zips(zip_path, work_dir):
            _load_inner_zip(con, inner_path, work_dir)
            loaded += 1
        load_done = time.monotonic()
        logger.info(
            "event=load_done nested_zips=%d elapsed_s=%.1f",
            loaded,
            load_done - download_done,
        )

        basket = load_basket(active_basket_path())
        _prepare_tables(con, settings, basket)
        prepare_done = time.monotonic()
        logger.info("event=transform_done elapsed_s=%.1f", prepare_done - load_done)

        result.rows = _write_outputs(con, settings, target_date)
        write_done = time.monotonic()

        out_of_scope = con.execute(
            """
            SELECT COUNT(*) FROM productos_base
            WHERE provincia IS NOT NULL AND UPPER(TRIM(provincia)) NOT IN ({scope})
            """.format(scope=", ".join(f"'{p}'" for p in settings.scope_provinces))
        ).fetchone()
        counts = con.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM productos_raw),
              (SELECT COUNT(*) FROM sucursales_raw),
              (SELECT COUNT(*) FROM comercios_raw),
              (SELECT COUNT(*) FROM productos_scope),
              (SELECT COUNT(*) FROM productos_dedup),
              (SELECT COUNT(*) FROM top_eans)
            """
        ).fetchone()
        result.timings = {
            "download_s": round(download_done - started, 3),
            "load_s": round(load_done - download_done, 3),
            "transform_s": round(prepare_done - load_done, 3),
            "write_s": round(write_done - prepare_done, 3),
            "total_s": round(write_done - started, 3),
        }
        result.peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert counts is not None
        payload = {
            **result.as_dict(),
            "source": result.source,
            "counts": {
                "productos_raw": int(counts[0]),
                "sucursales_raw": int(counts[1]),
                "comercios_raw": int(counts[2]),
                "productos_scope": int(counts[3]),
                "productos_dedup": int(counts[4]),
                "top_eans": int(counts[5]),
                "out_of_scope": int(out_of_scope[0]) if out_of_scope else 0,
            },
            "settings": {
                "scope_provinces": list(settings.scope_provinces),
                "top_n_eans": settings.top_n_eans,
            },
        }
        _write_meta(settings, target_date, payload)
        logger.info(
            "event=ingest_ok fecha=%s rows=%s timings=%s",
            target_date.isoformat(),
            result.rows,
            result.timings,
        )
        return result
    finally:
        if con is not None:
            con.close()
        if not keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
            shutil.rmtree(settings.duckdb_temp_dir, ignore_errors=True)
            settings.duckdb_temp_dir.mkdir(parents=True, exist_ok=True)
