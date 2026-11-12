"""Materializa los marts livianos que consume el dashboard."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from canasta.basket import Basket, active_basket_path, load_basket
from canasta.config import Settings
from canasta.index import build_index
from canasta.ranking import rank_chains


def _write(columns: dict[str, list[Any]], target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    table = pa.table(columns)
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, target)
    return table.num_rows


def _scope_sql(scope: tuple[str, ...]) -> tuple[str, list[str]]:
    if not scope:
        return "1=1", []
    placeholders = ", ".join("?" for _ in scope)
    return f"provincia in ({placeholders})", list(scope)


def _daily_prices(
    con: duckdb.DuckDBPyConnection, scope: tuple[str, ...]
) -> dict[date, dict[str, float]]:
    where, params = _scope_sql(scope)
    rows = con.execute(
        f"""
        select fecha, ean, median(precio_lista) as precio
        from main_marts.fct_precio_diario
        where {where}
        group by 1, 2
        """,
        params,
    ).fetchall()
    prices: dict[date, dict[str, float]] = {}
    for day, ean, price in rows:
        prices.setdefault(day, {})[ean] = float(price)
    return prices


def _chain_prices(
    con: duckdb.DuckDBPyConnection, scope: tuple[str, ...], day: date
) -> dict[str, dict[str, float]]:
    where, params = _scope_sql(scope)
    rows = con.execute(
        f"""
        select cadena, ean, median(precio_lista) as precio
        from main_marts.fct_precio_diario
        where fecha = ? and {where}
        group by 1, 2
        """,
        [day, *params],
    ).fetchall()
    prices: dict[str, dict[str, float]] = {}
    for chain, ean, price in rows:
        prices.setdefault(chain, {})[ean] = float(price)
    return prices


def _presentacion(cantidad: Any, unidad: Any) -> str | None:
    def as_str(value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value).strip()

    return " ".join(part for part in (as_str(cantidad), as_str(unidad)) if part) or None


def _catalog_rows(con: duckdb.DuckDBPyConnection, day: date) -> list[dict[str, Any]]:
    """Catálogo de los EANs tracked: lo que el builder de la UI ofrece."""
    rows = con.execute(
        """
        select p.ean,
               p.descripcion,
               p.marca,
               p.cantidad_presentacion,
               p.unidad_presentacion,
               count(distinct f.cadena) as n_cadenas
        from main_marts.dim_producto p
        left join main_marts.fct_precio_diario f
               on f.ean = p.ean and f.fecha = ?
        group by 1, 2, 3, 4, 5
        """,
        [day],
    ).fetchall()
    catalog = []
    for ean, descripcion, marca, cantidad, unidad, n_cadenas in rows:
        catalog.append(
            {
                "ean": ean,
                "descripcion": descripcion,
                "marca": marca,
                "presentacion": _presentacion(cantidad, unidad),
                "n_cadenas": int(n_cadenas),
            }
        )
    catalog.sort(key=lambda row: row["descripcion"] or "")
    return catalog


def _precio_ean_diario_rows(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Mediana por fecha × provincia × EAN de los tracked, para el índice de cualquier canasta."""
    rows = con.execute(
        """
        select fecha, provincia, ean, median(precio_lista) as precio
        from main_marts.fct_precio_diario
        group by 1, 2, 3
        """
    ).fetchall()
    return [
        {"fecha": day, "provincia": provincia, "ean": ean, "precio": float(precio)}
        for day, provincia, ean, precio in rows
    ]


def _precio_ean_cadena_rows(con: duckdb.DuckDBPyConnection, day: date) -> list[dict[str, Any]]:
    """Mediana por provincia × cadena × EAN de la última fecha, para el ranking."""
    rows = con.execute(
        """
        select provincia, cadena, ean, median(precio_lista) as precio
        from main_marts.fct_precio_diario
        where fecha = ?
        group by 1, 2, 3
        """,
        [day],
    ).fetchall()
    return [
        {
            "fecha": day,
            "provincia": provincia,
            "cadena": cadena,
            "ean": ean,
            "precio": float(precio),
        }
        for provincia, cadena, ean, precio in rows
    ]


def _detail_rows(
    con: duckdb.DuckDBPyConnection,
    scope: tuple[str, ...],
    day: date,
    basket: Basket,
) -> list[dict[str, Any]]:
    where, params = _scope_sql(scope)
    rows = con.execute(
        f"""
        select cadena, ean, median(precio_lista) as precio
        from main_marts.fct_precio_diario
        where fecha = ? and {where}
        group by 1, 2
        """,
        [day, *params],
    ).fetchall()
    by_ean = {item.ean: item for item in basket.items}
    detail = []
    for chain, ean, price in rows:
        item = by_ean.get(ean)
        if item is None:
            continue
        detail.append(
            {
                "fecha": day,
                "cadena": chain,
                "ean": ean,
                "label": item.label,
                "qty_per_month": item.qty_per_month,
                "precio": float(price),
                "costo": item.qty_per_month * float(price),
            }
        )
    detail.sort(key=lambda row: (row["cadena"], row["label"]))
    return detail


def _health(
    con: duckdb.DuckDBPyConnection, settings: Settings, day: date, coverage: float
) -> dict[str, Any]:
    meta_path = settings.raw_dir / "_meta" / f"fecha={day.isoformat()}" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rejects_path = settings.raw_dir / "rejects" / f"fecha={day.isoformat()}" / "part.parquet"
    rejects = 0
    if rejects_path.exists():
        row = con.execute(
            f"select coalesce(sum(n), 0) from read_parquet('{rejects_path.as_posix()}')"
        ).fetchone()
        rejects = int(row[0]) if row else 0
    return {
        "fecha": day,
        "productos_raw": meta["counts"]["productos_raw"],
        "productos_scope": meta["counts"]["productos_scope"],
        "productos_dedup": meta["counts"]["productos_dedup"],
        "sucursales": meta["rows"]["sucursales"],
        "comercios": meta["rows"]["comercios"],
        "rechazos": rejects,
        "cobertura_canasta": coverage,
        "fuente_bytes": meta["source"].get("bytes", 0),
    }


def write_marts(settings: Settings, basket_path: Path | None = None) -> dict[str, int]:
    basket = load_basket(basket_path or active_basket_path())
    if not basket.items:
        raise ValueError("la canasta está vacía")
    db_path = settings.data_dir / "canasta.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(f"falta {db_path}; corré `make dbt` primero")

    scope = basket.provincias or settings.scope_provinces
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        prices = _daily_prices(con, scope)
        if not prices:
            raise ValueError("no hay precios para el alcance de la canasta")
        latest = max(prices)
        chain_prices = _chain_prices(con, scope, latest)
        index = build_index(
            prices,
            basket.items,
            max_carry_forward_days=settings.max_carry_forward_days,
            min_coverage_pct=settings.min_coverage_pct,
        )
        ranking = rank_chains(
            chain_prices, basket.items, min_coverage_pct=settings.min_coverage_pct
        )
        detail = _detail_rows(con, scope, latest, basket)
        catalog = _catalog_rows(con, latest)
        precio_diario = _precio_ean_diario_rows(con)
        precio_cadena = _precio_ean_cadena_rows(con, latest)
        health = _health(con, settings, latest, index.rows[-1].cobertura)
    finally:
        con.close()

    out = settings.marts_dir
    counts = {}
    counts["indice"] = _write(
        {
            "fecha": [row.fecha for row in index.rows],
            "costo": [row.costo for row in index.rows],
            "cobertura": [row.cobertura for row in index.rows],
            "completo": [row.completo for row in index.rows],
            "indice": [row.indice for row in index.rows],
            "n_items": [row.n_items for row in index.rows],
            "n_items_con_precio": [row.n_items_con_precio for row in index.rows],
            "base_fecha": [index.base_fecha for _ in index.rows],
            "base_costo": [index.base_costo for _ in index.rows],
        },
        out / "mart_indice_canasta.parquet",
    )
    counts["ranking"] = _write(
        {
            "fecha": [latest for _ in ranking.cadenas],
            "cadena": [row.cadena for row in ranking.cadenas],
            "costo": [row.costo for row in ranking.cadenas],
            "cobertura": [row.cobertura for row in ranking.cadenas],
            "completo": [row.completo for row in ranking.cadenas],
            "ranking": [row.ranking for row in ranking.cadenas],
            "mejor_cadena": [ranking.mejor_cadena for _ in ranking.cadenas],
            "costo_mejor_cadena": [ranking.costo_mejor_cadena for _ in ranking.cadenas],
            "costo_surtido": [ranking.costo_surtido for _ in ranking.cadenas],
            "ahorro_potencial": [ranking.ahorro_potencial for _ in ranking.cadenas],
            "cobertura_surtido": [ranking.cobertura_surtido for _ in ranking.cadenas],
        },
        out / "mart_ranking_cadenas.parquet",
    )
    detail_columns = ["fecha", "cadena", "ean", "label", "qty_per_month", "precio", "costo"]
    counts["detalle"] = _write(
        {key: [row[key] for row in detail] for key in detail_columns},
        out / "mart_canasta_detalle.parquet",
    )
    counts["salud"] = _write(
        {key: [value] for key, value in health.items()}, out / "mart_salud.parquet"
    )
    counts["catalogo"] = _write(
        {
            "ean": [row["ean"] for row in catalog],
            "descripcion": [row["descripcion"] for row in catalog],
            "marca": [row["marca"] for row in catalog],
            "presentacion": [row["presentacion"] for row in catalog],
            "n_cadenas": [row["n_cadenas"] for row in catalog],
        },
        out / "mart_catalogo.parquet",
    )
    counts["precio_ean_diario"] = _write(
        {
            "fecha": [row["fecha"] for row in precio_diario],
            "provincia": [row["provincia"] for row in precio_diario],
            "ean": [row["ean"] for row in precio_diario],
            "precio": [row["precio"] for row in precio_diario],
        },
        out / "mart_precio_ean_diario.parquet",
    )
    counts["precio_ean_cadena"] = _write(
        {
            "fecha": [row["fecha"] for row in precio_cadena],
            "provincia": [row["provincia"] for row in precio_cadena],
            "cadena": [row["cadena"] for row in precio_cadena],
            "ean": [row["ean"] for row in precio_cadena],
            "precio": [row["precio"] for row in precio_cadena],
        },
        out / "mart_precio_ean_cadena.parquet",
    )
    return counts
