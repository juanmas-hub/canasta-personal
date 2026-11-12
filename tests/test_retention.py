"""Poda de particiones raw: respeta la retención de detalle y de agregados."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from canasta.config import Settings
from canasta.retention import prune_raw


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        tmp_dir=tmp_path / "tmp",
        duckdb_temp_dir=tmp_path / "duckdb_tmp",
        scope_provinces=("AR-C",),
        top_n_eans=10,
        detail_retention_days=90,
        agg_retention_days=365,
        volume_tolerance_pct=30.0,
        max_carry_forward_days=3,
        min_coverage_pct=90.0,
    )


def test_prune_raw_respeta_retenciones(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    today = date(2026, 11, 10)
    old_detail = settings.raw_dir / "fct_precio_diario" / "fecha=2026-08-01"
    new_detail = settings.raw_dir / "fct_precio_diario" / "fecha=2026-09-01"
    old_agg = settings.raw_dir / "agg_precio_ean_diario" / "fecha=2025-10-01"
    new_agg = settings.raw_dir / "agg_precio_ean_diario" / "fecha=2026-01-01"
    for path in (old_detail, new_detail, old_agg, new_agg):
        path.mkdir(parents=True)

    removed = prune_raw(settings, today=today)

    assert not old_detail.exists()
    assert new_detail.exists()
    assert not old_agg.exists()
    assert new_agg.exists()
    assert removed["fct_precio_diario"] == 1
    assert removed["agg_precio_ean_diario"] == 1
