"""Genera Parquet mínimos para correr `dbt build` sin datos reales."""

# ruff: noqa: E501

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "raw"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    con = duckdb.connect()

    con.execute(
        """
        create table fct (
            fecha date, id_comercio varchar, id_bandera varchar, id_sucursal varchar,
            ean varchar, descripcion varchar, marca varchar, precio_lista double,
            precio_referencia double, cantidad_referencia double,
            unidad_referencia varchar, cantidad_presentacion double,
            unidad_presentacion varchar, promo1 double, promo2 double,
            provincia varchar, localidad varchar, cadena varchar
        )
        """
    )
    rows = [
        (
            "2026-11-01",
            "1",
            "1",
            "1",
            "7790000000010",
            "Leche 1 L",
            "Marca",
            100,
            None,
            1,
            "L",
            1,
            "L",
            None,
            None,
            "AR-C",
            "CABA",
            "Super A",
        ),
        (
            "2026-11-01",
            "1",
            "1",
            "1",
            "7790000000027",
            "Pan 500 g",
            "Marca",
            200,
            None,
            1,
            "kg",
            0.5,
            "kg",
            None,
            None,
            "AR-C",
            "CABA",
            "Super A",
        ),
        (
            "2026-11-01",
            "2",
            "2",
            "2",
            "7790000000010",
            "Leche 1 L",
            "Marca",
            90,
            None,
            1,
            "L",
            1,
            "L",
            None,
            None,
            "AR-C",
            "CABA",
            "Super B",
        ),
        (
            "2026-11-01",
            "2",
            "2",
            "2",
            "7790000000027",
            "Pan 500 g",
            "Marca",
            210,
            None,
            1,
            "kg",
            0.5,
            "kg",
            None,
            None,
            "AR-C",
            "CABA",
            "Super B",
        ),
        (
            "2026-11-01",
            "3",
            "3",
            "3",
            "7790000000010",
            "Leche 1 L",
            "Marca",
            80,
            None,
            1,
            "L",
            1,
            "L",
            None,
            None,
            "AR-C",
            "CABA",
            "Super C",
        ),
        (
            "2026-11-02",
            "1",
            "1",
            "1",
            "7790000000010",
            "Leche 1 L",
            "Marca",
            110,
            None,
            1,
            "L",
            1,
            "L",
            None,
            None,
            "AR-C",
            "CABA",
            "Super A",
        ),
        (
            "2026-11-02",
            "1",
            "1",
            "1",
            "7790000000027",
            "Pan 500 g",
            "Marca",
            220,
            None,
            1,
            "kg",
            0.5,
            "kg",
            None,
            None,
            "AR-C",
            "CABA",
            "Super A",
        ),
        (
            "2026-11-02",
            "2",
            "2",
            "2",
            "7790000000010",
            "Leche 1 L",
            "Marca",
            99,
            None,
            1,
            "L",
            1,
            "L",
            None,
            None,
            "AR-C",
            "CABA",
            "Super B",
        ),
        (
            "2026-11-02",
            "2",
            "2",
            "2",
            "7790000000027",
            "Pan 500 g",
            "Marca",
            230,
            None,
            1,
            "kg",
            0.5,
            "kg",
            None,
            None,
            "AR-C",
            "CABA",
            "Super B",
        ),
    ]
    con.executemany("insert into fct values (" + ",".join(["?"] * 18) + ")", rows)
    for day in ("2026-11-01", "2026-11-02"):
        target = OUT / "fct_precio_diario" / f"fecha={day}"
        target.mkdir(parents=True)
        con.execute(
            f"copy (select * from fct where fecha = date '{day}') "
            f"to '{target.as_posix()}/part.parquet' (format parquet)"
        )

    con.execute(
        """
        create table agg (
            fecha date, ean varchar, provincia varchar, "min" double, p25 double,
            mediana double, p75 double, "max" double, n_sucursales bigint,
            n_observaciones bigint
        )
        """
    )
    agg_rows = [
        ("2026-11-01", "7790000000010", "AR-C", 80, 85, 90, 95, 100, 3, 3),
        ("2026-11-01", "7790000000027", "AR-C", 200, 205, 205, 207.5, 210, 2, 2),
        ("2026-11-02", "7790000000010", "AR-C", 99, 104.5, 104.5, 106.75, 110, 2, 2),
        ("2026-11-02", "7790000000027", "AR-C", 220, 225, 225, 227.5, 230, 2, 2),
    ]
    con.executemany("insert into agg values (" + ",".join(["?"] * 10) + ")", agg_rows)
    for day in ("2026-11-01", "2026-11-02"):
        target = OUT / "agg_precio_ean_diario" / f"fecha={day}"
        target.mkdir(parents=True)
        con.execute(
            f"copy (select * from agg where fecha = date '{day}') "
            f"to '{target.as_posix()}/part.parquet' (format parquet)"
        )

    con.execute(
        """
        create table sucursales (
            id_comercio varchar, id_bandera varchar, id_sucursal varchar,
            sucursales_nombre varchar, sucursales_tipo varchar, sucursales_calle varchar,
            sucursales_numero varchar, sucursales_latitud double, sucursales_longitud double,
            sucursales_barrio varchar, sucursales_codigo_postal varchar,
            sucursales_localidad varchar, sucursales_provincia varchar, fecha date
        )
        """
    )
    suc_rows = [
        (
            "1",
            "1",
            "1",
            "Sucursal A",
            "Supermercado",
            "Calle",
            "1",
            -34.6,
            -58.4,
            "Centro",
            "1000",
            "CABA",
            "AR-C",
            "2026-11-01",
        ),
        (
            "2",
            "2",
            "2",
            "Sucursal B",
            "Supermercado",
            "Calle",
            "2",
            -34.6,
            -58.4,
            "Centro",
            "1000",
            "CABA",
            "AR-C",
            "2026-11-01",
        ),
        (
            "3",
            "3",
            "3",
            "Sucursal C",
            "Supermercado",
            "Calle",
            "3",
            -34.6,
            -58.4,
            "Centro",
            "1000",
            "CABA",
            "AR-C",
            "2026-11-01",
        ),
    ]
    con.executemany("insert into sucursales values (" + ",".join(["?"] * 14) + ")", suc_rows)
    target = OUT / "sucursales" / "fecha=2026-11-01"
    target.mkdir(parents=True)
    con.execute(f"copy sucursales to '{target.as_posix()}/part.parquet' (format parquet)")

    con.execute(
        """
        create table comercios (
            id_comercio varchar, id_bandera varchar, comercio_razon_social varchar,
            comercio_bandera_nombre varchar, fecha date
        )
        """
    )
    com_rows = [
        ("1", "1", "Super A SA", "Super A", "2026-11-01"),
        ("2", "2", "Super B SA", "Super B", "2026-11-01"),
        ("3", "3", "Super C SA", "Super C", "2026-11-01"),
    ]
    con.executemany("insert into comercios values (" + ",".join(["?"] * 5) + ")", com_rows)
    target = OUT / "comercios" / "fecha=2026-11-01"
    target.mkdir(parents=True)
    con.execute(f"copy comercios to '{target.as_posix()}/part.parquet' (format parquet)")

    con.execute("create table basket (ean varchar, label varchar, qty_per_month double)")
    con.executemany(
        "insert into basket values (?, ?, ?)",
        [("7790000000010", "Leche 1 L", 2), ("7790000000027", "Pan 500 g", 1)],
    )
    con.execute(f"copy basket to '{(OUT / 'basket_items.parquet').as_posix()}' (format parquet)")

    for day, productos in (("2026-11-01", 6), ("2026-11-02", 4)):
        meta_dir = OUT / "_meta" / f"fecha={day}"
        meta_dir.mkdir(parents=True)
        meta = {
            "date": day,
            "counts": {
                "productos_raw": productos,
                "productos_scope": productos,
                "productos_dedup": productos,
            },
            "rows": {"sucursales": 3, "comercios": 3},
            "source": {"bytes": 0},
        }
        (meta_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"fixtures: {OUT}")


if __name__ == "__main__":
    main()
