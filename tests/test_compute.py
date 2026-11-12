"""Tests del cálculo en sesión del dashboard (marts genéricos -> índice y ranking)."""

from __future__ import annotations

import pandas as pd

from canasta.basket import BasketItem
from dashboard.compute import (
    chain_prices,
    compute_index,
    compute_ranking,
    daily_prices,
    detail_frame,
    last_daily_prices,
)

LECHE = "7790000000010"
PAN = "7790000000027"


def precio_diario() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": [
                "2026-11-01",
                "2026-11-01",
                "2026-11-02",
                "2026-11-02",
                "2026-11-01",
                "2026-11-02",
            ],
            "provincia": ["AR-C", "AR-B", "AR-C", "AR-B", "AR-C", "AR-C"],
            "ean": [LECHE] * 4 + [PAN, PAN],
            "precio": [100.0, 150.0, 110.0, 165.0, 50.0, 55.0],
        }
    )


def precio_cadena() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": ["2026-11-02"] * 6,
            "provincia": ["AR-C", "AR-C", "AR-B", "AR-B", "AR-C", "AR-C"],
            "cadena": ["Super A", "Super B", "Super A", "Super B", "Super A", "Super B"],
            "ean": [LECHE, LECHE, LECHE, LECHE, PAN, PAN],
            "precio": [110.0, 220.0, 165.0, 330.0, 55.0, 40.0],
        }
    )


def items() -> list[BasketItem]:
    return [
        BasketItem(ean=LECHE, label="Leche 1 L", qty_per_month=2.0),
        BasketItem(ean=PAN, label="Pan 500 g", qty_per_month=1.0),
    ]


def test_daily_prices_filtra_provincia() -> None:
    all_provinces = daily_prices(precio_diario(), [])
    # mediana entre AR-C (100) y AR-B (150)
    assert all_provinces[pd.Timestamp("2026-11-01").date()][LECHE] == 125.0

    only_c = daily_prices(precio_diario(), ["AR-C"])
    assert only_c[pd.Timestamp("2026-11-01").date()][LECHE] == 100.0


def test_compute_index_base_100() -> None:
    result = compute_index(precio_diario(), items(), ["AR-C"])
    assert result.base_fecha == pd.Timestamp("2026-11-01").date()
    first, second = result.rows
    assert first.costo == 250.0  # 2*100 + 1*50
    assert second.costo == 275.0  # 2*110 + 1*55
    assert second.indice == 110.0


def test_compute_ranking_y_detalle() -> None:
    result = compute_ranking(precio_cadena(), items(), ["AR-C"])
    assert result.mejor_cadena == "Super A"
    assert result.costo_mejor_cadena == 275.0  # 2*110 leche + 1*55 pan, todo en Super A
    assert result.costo_surtido == 260.0  # leche en A (110), pan en B (40)
    assert result.ahorro_potencial == 15.0

    detail = detail_frame(precio_cadena(), items(), ["AR-C"])
    super_a = detail[detail["cadena"] == "Super A"]
    assert set(super_a["label"]) == {"Leche 1 L", "Pan 500 g"}
    assert super_a["costo"].sum() == 275.0


def test_last_daily_prices() -> None:
    precios = last_daily_prices(precio_diario(), ["AR-C"])
    assert precios[LECHE] == 110.0
    assert precios[PAN] == 55.0


def test_chain_prices_filtra_provincia() -> None:
    only_b = chain_prices(precio_cadena(), ["AR-B"])
    assert only_b == {"Super A": {LECHE: 165.0}, "Super B": {LECHE: 330.0}}
