"""Helpers del builder de canasta: búsqueda en catálogo, export e import de basket.yml."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import yaml

from canasta.basket import Basket, BasketItem, load_basket


def search_catalog(catalog: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    query = query.strip().lower()
    if not query:
        return catalog.head(limit)
    descripcion = catalog["descripcion"].fillna("").str.lower()
    marca = catalog["marca"].fillna("").str.lower()
    mask = descripcion.str.contains(query, regex=False) | marca.str.contains(query, regex=False)
    return catalog[mask].head(limit)


def item_label(descripcion: str | None, marca: str | None, presentacion: str | None) -> str:
    parts = [p for p in (descripcion, marca, presentacion) if p]
    return " ".join(parts) if parts else "producto"


def merge_items(items: Sequence[BasketItem], rows: pd.DataFrame, qty: float) -> list[BasketItem]:
    by_ean = {item.ean: item for item in items}
    if qty <= 0:
        return list(by_ean.values())
    for _, row in rows.iterrows():
        ean = str(row["ean"])
        existing = by_ean.get(ean)
        label = (
            existing.label
            if existing
            else item_label(row.get("descripcion"), row.get("marca"), row.get("presentacion"))
        )
        current = existing.qty_per_month if existing else 0.0
        by_ean[ean] = BasketItem(ean=ean, label=label, qty_per_month=current + qty)
    return list(by_ean.values())


def basket_yaml(items: Sequence[BasketItem], provincias: Sequence[str]) -> str:
    payload = {
        "scope": {"provincias": list(provincias)},
        "items": [
            {"ean": item.ean, "label": item.label, "qty_per_month": item.qty_per_month}
            for item in items
        ],
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def parse_basket_upload(data: bytes) -> Basket:
    """Valida un basket.yml subido reusando load_basket (EAN y qty)."""
    with tempfile.NamedTemporaryFile("wb", suffix=".yml") as tmp:
        tmp.write(data)
        tmp.flush()
        return load_basket(Path(tmp.name))
