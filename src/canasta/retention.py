"""Poda de particiones raw viejas según la retención configurada."""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

from canasta.config import Settings


def _prune_table(raw_dir: Path, table: str, days: int, ref: date) -> int:
    cutoff = ref - timedelta(days=days)
    removed = 0
    for path in (raw_dir / table).glob("fecha=*"):
        try:
            day = date.fromisoformat(path.name.removeprefix("fecha="))
        except ValueError:
            continue
        if day < cutoff:
            shutil.rmtree(path)
            removed += 1
    return removed


def prune_raw(settings: Settings, today: date | None = None) -> dict[str, int]:
    ref = today or date.today()
    raw = settings.raw_dir
    return {
        "fct_precio_diario": _prune_table(
            raw, "fct_precio_diario", settings.detail_retention_days, ref
        ),
        "agg_precio_ean_diario": _prune_table(
            raw, "agg_precio_ean_diario", settings.agg_retention_days, ref
        ),
        "sucursales": _prune_table(raw, "sucursales", settings.agg_retention_days, ref),
        "comercios": _prune_table(raw, "comercios", settings.agg_retention_days, ref),
        "rejects": _prune_table(raw, "rejects", settings.agg_retention_days, ref),
        "_meta": _prune_table(raw, "_meta", settings.agg_retention_days, ref),
    }
