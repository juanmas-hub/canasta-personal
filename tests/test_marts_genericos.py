"""Tests de los marts genéricos que habilitan el builder de canasta en la UI."""

from __future__ import annotations

from datetime import date

import duckdb

from canasta.marts import (
    _catalog_rows,
    _precio_ean_cadena_rows,
    _precio_ean_diario_rows,
)


def make_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("create schema main_marts")
    con.execute(
        """
        create table main_marts.dim_producto (
            ean varchar,
            descripcion varchar,
            marca varchar,
            cantidad_presentacion varchar,
            unidad_presentacion varchar
        )
        """
    )
    con.execute(
        """
        create table main_marts.fct_precio_diario (
            fecha date,
            ean varchar,
            provincia varchar,
            cadena varchar,
            precio_lista double
        )
        """
    )
    con.executemany(
        "insert into main_marts.dim_producto values (?, ?, ?, ?, ?)",
        [
            ("7790000000010", "Leche entera 1 L", "La Serenisima", "1", "L"),
            ("7790000000027", "Pan lactal 500 g", "Lactal", "500", "g"),
        ],
    )
    con.executemany(
        "insert into main_marts.fct_precio_diario values (?, ?, ?, ?, ?)",
        [
            ("2026-11-01", "7790000000010", "AR-C", "Super A", 100.0),
            ("2026-11-01", "7790000000010", "AR-C", "Super B", 200.0),
            ("2026-11-01", "7790000000010", "AR-B", "Super A", 150.0),
            ("2026-11-01", "7790000000027", "AR-C", "Super A", 50.0),
            ("2026-11-02", "7790000000010", "AR-C", "Super A", 110.0),
            ("2026-11-02", "7790000000010", "AR-C", "Super B", 220.0),
            ("2026-11-02", "7790000000010", "AR-B", "Super A", 165.0),
            ("2026-11-02", "7790000000027", "AR-C", "Super A", 55.0),
        ],
    )
    return con


def test_catalogo_presentacion_y_cadenas() -> None:
    rows = _catalog_rows(make_con(), date(2026, 11, 2))

    by_ean = {row["ean"]: row for row in rows}
    leche = by_ean["7790000000010"]
    assert leche["descripcion"] == "Leche entera 1 L"
    assert leche["marca"] == "La Serenisima"
    assert leche["presentacion"] == "1 L"
    assert leche["n_cadenas"] == 2  # Super A y Super B
    pan = by_ean["7790000000027"]
    assert pan["presentacion"] == "500 g"
    assert pan["n_cadenas"] == 1


def test_precio_ean_diario_agrupa_por_fecha_provincia() -> None:
    rows = _precio_ean_diario_rows(make_con())

    by_key = {(row["fecha"], row["provincia"], row["ean"]): row["precio"] for row in rows}
    assert by_key[(date(2026, 11, 1), "AR-C", "7790000000010")] == 150.0  # mediana(100, 200)
    assert by_key[(date(2026, 11, 2), "AR-B", "7790000000010")] == 165.0
    assert by_key[(date(2026, 11, 2), "AR-C", "7790000000027")] == 55.0
    assert len(rows) == 6


def test_precio_ean_cadena_solo_ultima_fecha() -> None:
    rows = _precio_ean_cadena_rows(make_con(), date(2026, 11, 2))

    keys = {(row["provincia"], row["cadena"], row["ean"]) for row in rows}
    assert keys == {
        ("AR-C", "Super A", "7790000000010"),
        ("AR-C", "Super B", "7790000000010"),
        ("AR-B", "Super A", "7790000000010"),
        ("AR-C", "Super A", "7790000000027"),
    }
    assert all(row["fecha"] == date(2026, 11, 2) for row in rows)
    by_key = {(row["cadena"], row["ean"], row["provincia"]): row["precio"] for row in rows}
    assert by_key[("Super A", "7790000000010", "AR-C")] == 110.0
