import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from canasta.basket import Basket
from canasta.config import Settings
from canasta.ingest import (
    COMERCIO_COLUMNS,
    PRODUCTOS_COLUMNS,
    SUCURSALES_COLUMNS,
    SchemaError,
    _normalize_csv,
    run_ingest,
)


def _csv(columns: list[str], rows: list[dict[str, str]], newline: str = "\n") -> bytes:
    lines = ["|".join(columns)]
    for row in rows:
        lines.append("|".join(row.get(column, "") for column in columns))
    return newline.join(lines).encode("utf-8") + newline.encode("utf-8")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        tmp_dir=tmp_path / "tmp",
        duckdb_temp_dir=tmp_path / "duckdb_tmp",
        scope_provinces=("AR-C",),
        top_n_eans=2,
        detail_retention_days=90,
        agg_retention_days=365,
        volume_tolerance_pct=30,
        max_carry_forward_days=3,
        min_coverage_pct=90,
    )


def _sucursal(sucursal: str, provincia: str) -> dict[str, str]:
    return {
        "id_comercio": "1",
        "id_bandera": "1",
        "id_sucursal": sucursal,
        "sucursales_provincia": provincia,
    }


def _product(sucursal: str, ean: str, flag: str, price: str) -> dict[str, str]:
    return {
        "id_comercio": "1",
        "id_bandera": "1",
        "id_sucursal": sucursal,
        "id_producto": ean,
        "productos_ean": flag,
        "productos_descripcion": "Producto",
        "productos_precio_lista": price,
    }


def _nested_zip(tmp_path: Path) -> Path:
    comercios = _csv(
        COMERCIO_COLUMNS,
        [
            {
                "id_comercio": "1",
                "id_bandera": "1",
                "comercio_razon_social": "Test SA",
                "comercio_bandera_nombre": "Test",
            }
        ],
    )
    sucursales = _csv(
        SUCURSALES_COLUMNS,
        [
            _sucursal("1", "AR-C"),
            _sucursal("2", "AR-B"),
            _sucursal("3", "AR-C"),
        ],
    )
    productos = _csv(
        PRODUCTOS_COLUMNS,
        [
            _product("1", "4006381333931", "1", "100"),
            _product("3", "4006381333931", "1", "120"),
            _product("1", "96385074", "1", "50"),
            _product("1", "4006381333932", "1", "10"),
            _product("1", "123", "0", "10"),
            _product("1", "036000291452", "1", "0"),
            _product("2", "036000291452", "1", "30"),
            _product("3", "036000291452", "1", "40"),
        ],
    )
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("comercio.csv", comercios)
        zf.writestr("sucursales.csv", sucursales)
        zf.writestr("productos.csv", productos)
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as zf:
        zf.write(inner, "2026-11-03/inner.zip")
    return outer


def test_normalize_csv_handles_bom_crlf_nul_footer_and_header_spaces(tmp_path: Path) -> None:
    header = " | ".join(COMERCIO_COLUMNS)
    source = (
        b"\xef\xbb\xbf"
        + header.encode()
        + b"\r\n1|2|3|Test SA|Test|url|2026-11-03|1.0\r\n\x00\r\n"
        + b"Ultima actualizacion: 2026-11-03\r\n"
    )
    dest = tmp_path / "normalize.csv"
    _normalize_csv(io.BytesIO(source), dest, COMERCIO_COLUMNS)
    assert (
        dest.read_bytes()
        == ("|".join(COMERCIO_COLUMNS) + "\n1|2|3|Test SA|Test|url|2026-11-03|1.0\n").encode()
    )


def test_normalize_csv_rejects_new_columns(tmp_path: Path) -> None:
    source = ("|".join(COMERCIO_COLUMNS[:-1]) + "\n").encode()
    with pytest.raises(SchemaError):
        _normalize_csv(io.BytesIO(source), tmp_path / "bad.csv", COMERCIO_COLUMNS)


def test_run_ingest_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    for directory in (settings.tmp_dir, settings.duckdb_temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
    outer = _nested_zip(tmp_path)

    monkeypatch.setattr("canasta.ingest.load_basket", lambda path: Basket(provincias=(), items=()))

    result = run_ingest(date(2026, 11, 3), settings, zip_path=outer)

    assert result.rows == {
        "agg_precio_ean_diario": 3,
        "fct_precio_diario": 3,
        "sucursales": 2,
        "comercios": 1,
        "rejects": 3,
        "basket_items": 0,
    }
    meta = settings.raw_dir / "_meta" / "fecha=2026-11-03" / "meta.json"
    assert meta.exists()
    assert not (settings.tmp_dir / "ingest_2026-11-03").exists()
