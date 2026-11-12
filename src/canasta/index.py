"""Índice de canasta propia: base 100, cobertura y carry-forward."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from canasta.basket import BasketItem


@dataclass(frozen=True)
class IndexRow:
    fecha: date
    costo: float | None
    cobertura: float
    completo: bool
    indice: float | None
    n_items: int
    n_items_con_precio: int


@dataclass(frozen=True)
class IndexResult:
    rows: tuple[IndexRow, ...]
    base_fecha: date | None
    base_costo: float | None


def build_index(
    prices: Mapping[date, Mapping[str, float]],
    items: Sequence[BasketItem],
    *,
    max_carry_forward_days: int = 3,
    min_coverage_pct: float = 90.0,
) -> IndexResult:
    """Calcula el índice con precios diarios por EAN ya agregados al alcance."""
    total_weight = sum(item.qty_per_month for item in items)
    if not items or total_weight <= 0:
        return IndexResult(rows=(), base_fecha=None, base_costo=None)

    last_seen: dict[str, tuple[date, float]] = {}
    rows: list[IndexRow] = []
    base_fecha: date | None = None
    base_costo: float | None = None

    for day in sorted(prices):
        cost = 0.0
        covered_weight = 0.0
        n_with_price = 0
        for item in items:
            price = prices[day].get(item.ean)
            if price is not None and price > 0:
                last_seen[item.ean] = (day, price)
            else:
                seen = last_seen.get(item.ean)
                if seen and (day - seen[0]).days <= max_carry_forward_days:
                    price = seen[1]
                else:
                    price = None
            if price is not None:
                cost += item.qty_per_month * price
                covered_weight += item.qty_per_month
                n_with_price += 1

        coverage = covered_weight / total_weight * 100
        complete = coverage >= min_coverage_pct
        if complete and base_fecha is None:
            base_fecha = day
            base_costo = cost

        index = None
        if base_costo and base_costo > 0 and base_fecha is not None and day >= base_fecha:
            index = 100 * cost / base_costo

        rows.append(
            IndexRow(
                fecha=day,
                costo=cost if n_with_price else None,
                cobertura=coverage,
                completo=complete,
                indice=index,
                n_items=len(items),
                n_items_con_precio=n_with_price,
            )
        )

    return IndexResult(rows=tuple(rows), base_fecha=base_fecha, base_costo=base_costo)
