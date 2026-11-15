"""Tests del builder: búsqueda en catálogo y roundtrip basket.yml."""

from __future__ import annotations

import pandas as pd

from canasta.basket import BasketItem
from dashboard.builder import (
    basket_yaml,
    merge_items,
    merge_selection,
    parse_basket_upload,
    search_catalog,
)


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


def test_merge_items_agrega_nuevo() -> None:
    rows = catalog().head(1).assign(qty=2.0)
    items = merge_items([], rows)

    assert len(items) == 1
    assert items[0].ean == "7790000000010"
    assert items[0].label == "Leche entera 1 L La Serenisima 1 L"
    assert items[0].qty_per_month == 2.0


def test_merge_items_suma_duplicado() -> None:
    existing = [BasketItem(ean="7790000000010", label="Leche", qty_per_month=3.0)]
    items = merge_items(existing, catalog().head(1).assign(qty=2.0))

    assert len(items) == 1
    assert items[0].label == "Leche"
    assert items[0].qty_per_month == 5.0


def test_merge_items_ignora_cantidad_invalida() -> None:
    existing = [BasketItem(ean="7790000000010", label="Leche", qty_per_month=3.0)]
    items = merge_items(existing, catalog().assign(qty=0.0))

    assert len(items) == 1
    assert items[0].qty_per_month == 3.0


def test_merge_items_cantidades_distintas_por_producto() -> None:
    items = merge_items([], catalog().assign(qty=[2.0, 3.0]))

    assert {item.ean: item.qty_per_month for item in items} == {
        "7790000000010": 2.0,
        "7790000000027": 3.0,
    }


def test_merge_items_sin_columna_qty_no_agrega() -> None:
    assert merge_items([], catalog()) == []


def test_merge_selection_conserva_al_cambiar_busqueda() -> None:
    selected = {"A": {"ean": "A"}}
    per_query = {"queso": {"A"}}

    merged, per = merge_selection(selected, per_query, "queso", "leche", {})

    assert merged == selected
    assert per == per_query


def test_merge_selection_suma_en_la_misma_busqueda() -> None:
    now = {"A": {"ean": "A"}, "B": {"ean": "B"}}
    merged, per = merge_selection({"A": {"ean": "A"}}, {"queso": {"A"}}, "queso", "queso", now)

    assert set(merged) == {"A", "B"}
    assert per["queso"] == {"A", "B"}


def test_merge_selection_desmarca_solo_ese_ean() -> None:
    selected = {"A": {"ean": "A"}, "B": {"ean": "B"}}
    merged, per = merge_selection(
        selected, {"queso": {"A", "B"}}, "queso", "queso", {"A": {"ean": "A"}}
    )

    assert set(merged) == {"A"}
    assert per["queso"] == {"A"}


def test_merge_selection_acumula_entre_busquedas() -> None:
    merged, per = merge_selection({"A": {"ean": "A"}}, {"queso": {"A"}}, "queso", "leche", {})
    merged, per = merge_selection(merged, per, "leche", "leche", {"B": {"ean": "B"}})

    assert set(merged) == {"A", "B"}
    assert per == {"queso": {"A"}, "leche": {"B"}}


def test_merge_selection_volver_a_busqueda_anterior_conserva() -> None:
    selected = {"A": {"ean": "A"}}

    merged, per = merge_selection(selected, {"queso": {"A"}}, "leche", "queso", {})

    assert merged == selected
    assert per == {"queso": {"A"}}
