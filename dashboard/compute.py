"""Cálculo en sesión del índice y el ranking para la canasta que armó el usuario."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd

from canasta.basket import BasketItem
from canasta.index import IndexResult, build_index
from canasta.ranking import RankingResult, rank_chains

MAX_CARRY_FORWARD_DAYS = 3
MIN_COVERAGE_PCT = 90.0


def _filtered(df: pd.DataFrame, provincias: Sequence[str]) -> pd.DataFrame:
    # shortcut: con varias provincias es mediana de medianas provinciales; exacta con una sola
    if provincias:
        df = df[df["provincia"].isin(provincias)]
    return df


def daily_prices(df: pd.DataFrame, provincias: Sequence[str]) -> dict[date, dict[str, float]]:
    df = _filtered(df, provincias)
    df = df.assign(fecha=pd.to_datetime(df["fecha"]).dt.date)
    prices: dict[date, dict[str, float]] = {}
    for (day, ean), precio in df.groupby(["fecha", "ean"])["precio"].median().items():
        prices.setdefault(day, {})[ean] = float(precio)
    return prices


def chain_prices(df: pd.DataFrame, provincias: Sequence[str]) -> dict[str, dict[str, float]]:
    df = _filtered(df, provincias)
    prices: dict[str, dict[str, float]] = {}
    for (cadena, ean), precio in df.groupby(["cadena", "ean"])["precio"].median().items():
        prices.setdefault(cadena, {})[ean] = float(precio)
    return prices


def last_daily_prices(df: pd.DataFrame, provincias: Sequence[str]) -> dict[str, float]:
    df = _filtered(df, provincias)
    df = df.assign(fecha=pd.to_datetime(df["fecha"]).dt.date)
    latest = df["fecha"].max()
    day = df[df["fecha"] == latest]
    return {ean: float(precio) for ean, precio in day.groupby("ean")["precio"].median().items()}


def compute_index(
    precio_diario: pd.DataFrame, items: Sequence[BasketItem], provincias: Sequence[str]
) -> IndexResult:
    return build_index(
        daily_prices(precio_diario, provincias),
        items,
        max_carry_forward_days=MAX_CARRY_FORWARD_DAYS,
        min_coverage_pct=MIN_COVERAGE_PCT,
    )


def compute_ranking(
    precio_cadena: pd.DataFrame, items: Sequence[BasketItem], provincias: Sequence[str]
) -> RankingResult:
    return rank_chains(
        chain_prices(precio_cadena, provincias), items, min_coverage_pct=MIN_COVERAGE_PCT
    )


def index_frame(result: IndexResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fecha": row.fecha,
                "costo": row.costo,
                "cobertura": row.cobertura,
                "completo": row.completo,
                "indice": row.indice,
                "n_items": row.n_items,
                "n_items_con_precio": row.n_items_con_precio,
            }
            for row in result.rows
        ]
    )


def ranking_frame(result: RankingResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cadena": row.cadena,
                "costo": row.costo,
                "cobertura": row.cobertura,
                "completo": row.completo,
                "ranking": row.ranking,
            }
            for row in result.cadenas
        ]
    )


def detail_frame(
    precio_cadena: pd.DataFrame,
    items: Sequence[BasketItem],
    provincias: Sequence[str],
) -> pd.DataFrame:
    columns = ["cadena", "ean", "label", "qty_per_month", "precio", "costo"]
    df = _filtered(precio_cadena, provincias)
    df = df[df["ean"].isin({item.ean for item in items})]
    medians = df.groupby(["cadena", "ean"])["precio"].median().reset_index()
    if medians.empty:
        return pd.DataFrame(columns=columns)
    by_ean = {item.ean: item for item in items}
    rows = []
    for _, row in medians.iterrows():
        item = by_ean[row["ean"]]
        rows.append(
            {
                "cadena": row["cadena"],
                "ean": item.ean,
                "label": item.label,
                "qty_per_month": item.qty_per_month,
                "precio": float(row["precio"]),
                "costo": item.qty_per_month * float(row["precio"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["cadena", "label"]).reset_index(drop=True)
