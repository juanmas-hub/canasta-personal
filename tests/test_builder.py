"""Tests del builder: búsqueda en catálogo y roundtrip basket.yml."""

from __future__ import annotations

import pandas as pd

from canasta.basket import BasketItem
from dashboard.builder import basket_yaml, parse_basket_upload, search_catalog


def catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ean": "7790000000010",
                "descripcion": "Leche entera 1 L",
                "marca": "La Serenisima",
                "presentacion": "1 L",
                "n_cadenas": 3,
            },
            {
                "ean": "7790000000027",
                "descripcion": "Pan lactal 500 g",
                "marca": "Lactal",
                "presentacion": "500 g",
                "n_cadenas": 1,
            },
        ]
    )


def test_search_catalog_case_insensitive() -> None:
    result = search_catalog(catalog(), "SERENISIMA")
    assert len(result) == 1
    assert result.iloc[0]["ean"] == "7790000000010"

    assert len(search_catalog(catalog(), "leche")) == 1
    assert search_catalog(catalog(), "noexiste").empty
    assert len(search_catalog(catalog(), "")) == 2


def test_basket_yaml_roundtrip() -> None:
    yaml_text = basket_yaml(
        [BasketItem(ean="7790000000010", label="Leche entera 1 L", qty_per_month=8.0)],
        ["AR-C"],
    )
    basket = parse_basket_upload(yaml_text.encode("utf-8"))

    assert basket.provincias == ("AR-C",)
    assert len(basket.items) == 1
    item = basket.items[0]
    assert item.ean == "7790000000010"
    assert item.label == "Leche entera 1 L"
    assert item.qty_per_month == 8.0


def test_parse_basket_upload_rechaza_ean_invalido() -> None:
    try:
        parse_basket_upload(b"items:\n  - ean: '123'\n    qty_per_month: 1")
    except ValueError:
        pass
    else:
        raise AssertionError("un EAN inválido debe rechazarse")
