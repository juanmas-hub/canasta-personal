"""Environment-backed settings. All heavy paths live under ./data."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the CLI works without extra dependencies."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    tmp_dir: Path
    duckdb_temp_dir: Path
    scope_provinces: tuple[str, ...]
    top_n_eans: int
    detail_retention_days: int
    agg_retention_days: int
    volume_tolerance_pct: float
    max_carry_forward_days: int
    min_coverage_pct: float

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def marts_dir(self) -> Path:
        return self.data_dir / "marts"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"


def load_settings() -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    data_dir = _path(os.getenv("DATA_DIR", "./data"))
    tmp_dir = _path(os.getenv("TMPDIR", "./data/tmp"))
    duckdb_temp_dir = _path(os.getenv("DUCKDB_TEMP_DIR", "./data/duckdb_tmp"))
    for directory in (data_dir, tmp_dir, duckdb_temp_dir):
        directory.mkdir(parents=True, exist_ok=True)

    provinces = tuple(
        part.strip().upper()
        for part in os.getenv("SCOPE_PROVINCES", "AR-C,AR-B").split(",")
        if part.strip()
    )
    return Settings(
        data_dir=data_dir,
        tmp_dir=tmp_dir,
        duckdb_temp_dir=duckdb_temp_dir,
        scope_provinces=provinces,
        top_n_eans=int(os.getenv("TOP_N_EANS", "2500")),
        detail_retention_days=int(os.getenv("DETAIL_RETENTION_DAYS", "90")),
        agg_retention_days=int(os.getenv("AGG_RETENTION_DAYS", "365")),
        volume_tolerance_pct=float(os.getenv("VOLUME_TOLERANCE_PCT", "30")),
        max_carry_forward_days=int(os.getenv("MAX_CARRY_FORWARD_DAYS", "3")),
        min_coverage_pct=float(os.getenv("MIN_COVERAGE_PCT", "90")),
    )
