"""Ranking de cadenas y ahorro potencial para la canasta del usuario."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from canasta.basket import BasketItem


@dataclass(frozen=True)
class ChainRanking:
    cadena: str
    costo: float | None
    cobertura: float
    completo: bool
    ranking: int | None


@dataclass(frozen=True)
class RankingResult:
    cadenas: tuple[ChainRanking, ...]
    mejor_cadena: str | None
    costo_mejor_cadena: float | None
    costo_surtido: float | None
    ahorro_potencial: float | None
    cobertura_surtido: float


def rank_chains(
    prices: Mapping[str, Mapping[str, float]],
    items: Sequence[BasketItem],
    *,
    min_coverage_pct: float = 90.0,
) -> RankingResult:
    """`prices` es cadena -> EAN -> precio para un solo día."""
    total_weight = sum(item.qty_per_month for item in items)
    if not items or total_weight <= 0:
        return RankingResult((), None, None, None, None, 0.0)

    rows: list[ChainRanking] = []
    for chain, chain_prices in prices.items():
        cost = 0.0
        covered_weight = 0.0
        for item in items:
            price = chain_prices.get(item.ean)
            if price is not None and price > 0:
                cost += item.qty_per_month * price
                covered_weight += item.qty_per_month
        coverage = covered_weight / total_weight * 100
        rows.append(
            ChainRanking(
                cadena=chain,
                costo=cost if covered_weight else None,
                cobertura=coverage,
                completo=coverage >= min_coverage_pct,
                ranking=None,
            )
        )

    complete = sorted(
        (row for row in rows if row.completo),
        key=lambda row: row.costo if row.costo is not None else float("inf"),
    )
    ranked = [
        ChainRanking(
            cadena=row.cadena,
            costo=row.costo,
            cobertura=row.cobertura,
            completo=row.completo,
            ranking=position,
        )
        for position, row in enumerate(complete, start=1)
    ]
    incomplete = sorted(
        (row for row in rows if not row.completo),
        key=lambda row: row.cobertura,
        reverse=True,
    )

    best = ranked[0] if ranked else None

    surtido_cost = 0.0
    surtido_weight = 0.0
    for item in items:
        available = [
            chain_prices[item.ean]
            for chain_prices in prices.values()
            if chain_prices.get(item.ean) is not None and chain_prices[item.ean] > 0
        ]
        if available:
            surtido_cost += item.qty_per_month * min(available)
            surtido_weight += item.qty_per_month
    surtido_coverage = surtido_weight / total_weight * 100
    surtido = surtido_cost if surtido_weight else None
    saving = (
        best.costo - surtido
        if best is not None and best.costo is not None and surtido is not None
        else None
    )

    return RankingResult(
        cadenas=tuple(ranked + incomplete),
        mejor_cadena=best.cadena if best else None,
        costo_mejor_cadena=best.costo if best else None,
        costo_surtido=surtido,
        ahorro_potencial=saving,
        cobertura_surtido=surtido_coverage,
    )
