"""User basket definition (basket.yml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from canasta.ean import is_valid_ean


@dataclass(frozen=True)
class BasketItem:
    ean: str
    label: str
    qty_per_month: float


@dataclass(frozen=True)
class Basket:
    provincias: tuple[str, ...]
    items: tuple[BasketItem, ...]

    @property
    def eans(self) -> tuple[str, ...]:
        return tuple(item.ean for item in self.items)

    @property
    def total_weight(self) -> float:
        return sum(item.qty_per_month for item in self.items)


def active_basket_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "basket.yml"
    return path if path.exists() else root / "basket.example.yml"


def load_basket(path: Path) -> Basket:
    if not path.exists():
        return Basket(provincias=(), items=())
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    scope = raw.get("scope") or {}
    provincias = tuple(
        str(p).strip().upper() for p in scope.get("provincias", []) if str(p).strip()
    )
    items: list[BasketItem] = []
    for entry in raw.get("items", []):
        ean = str(entry["ean"]).strip()
        if not is_valid_ean(ean):
            raise ValueError(f"invalid EAN in basket: {ean!r}")
        qty = float(entry["qty_per_month"])
        if qty <= 0:
            raise ValueError(f"qty_per_month must be > 0 for EAN {ean}")
        items.append(BasketItem(ean=ean, label=str(entry.get("label", ean)), qty_per_month=qty))
    return Basket(provincias=provincias, items=tuple(items))
