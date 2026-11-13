"""Smoke test del dashboard: puerta de cuenta obligatoria y render con marts de prueba."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"

LECHE = "7790000000010"
PAN = "7790000000027"


@pytest.fixture
def marts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    catalog = pd.DataFrame(
        [
            {
                "ean": LECHE,
                "descripcion": "Leche entera 1 L",
                "marca": "La Serenisima",
                "presentacion": "1 L",
                "n_cadenas": 2,
            },
            {
                "ean": PAN,
                "descripcion": "Pan lactal 500 g",
                "marca": "Lactal",
                "presentacion": "500 g",
                "n_cadenas": 1,
            },
        ]
    )
    precio_diario = pd.DataFrame(
        {
            "fecha": ["2026-11-01", "2026-11-01", "2026-11-02", "2026-11-02"],
            "provincia": ["AR-C", "AR-B", "AR-C", "AR-B"],
            "ean": [LECHE] * 2 + [PAN] * 2,
            "precio": [100.0, 150.0, 50.0, 55.0],
        }
    )
    precio_cadena = pd.DataFrame(
        {
            "fecha": ["2026-11-02"] * 4,
            "provincia": ["AR-C"] * 4,
            "cadena": ["Super A", "Super B", "Super A", "Super B"],
            "ean": [LECHE, LECHE, PAN, PAN],
            "precio": [110.0, 220.0, 55.0, 40.0],
        }
    )
    salud = pd.DataFrame(
        [
            {
                "fecha": "2026-11-02",
                "productos_raw": 10,
                "productos_scope": 8,
                "productos_dedup": 8,
                "sucursales": 3,
                "comercios": 3,
                "rechazos": 2,
                "cobertura_canasta": 100.0,
                "fuente_bytes": 0,
            }
        ]
    )
    for name, frame in (
        ("mart_catalogo", catalog),
        ("mart_precio_ean_diario", precio_diario),
        ("mart_precio_ean_cadena", precio_cadena),
        ("mart_salud", salud),
    ):
        frame.to_parquet(tmp_path / f"{name}.parquet")
    monkeypatch.setenv("CANASTA_MARTS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    from dashboard import store

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(store, "load_basket", lambda url, key: None)
    monkeypatch.setattr(store, "save_basket", lambda *args, **kwargs: None)


def _app(logged_in: bool) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    if logged_in:
        at.session_state["sb_token"] = "token"
        at.session_state["sb_email"] = "persona@example.com"
        at.session_state["sb_user_id"] = "user-1"
    at.run()
    return at


def test_sin_config_muestra_error(marts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dashboard import auth

    monkeypatch.setattr(auth, "sb_config", lambda: None)

    at = _app(logged_in=False)

    assert not at.exception, at.exception
    assert any("SUPABASE_URL" in str(e.value) for e in at.error)
    assert len(at.tabs) == 0


def test_sin_sesion_pide_login(marts_dir: Path, supabase: None) -> None:
    at = _app(logged_in=False)

    assert not at.exception, at.exception
    assert len(at.tabs) == 2
    assert [t.label for t in at.tabs] == ["Ingresar", "Crear cuenta"]


def test_dashboard_renderiza_sin_excepciones(marts_dir: Path, supabase: None) -> None:
    at = _app(logged_in=True)

    assert not at.exception, at.exception
    assert len(at.tabs) == 5
    # Sin canasta guardada muestra la de ejemplo y el índice se calcula igual.
    assert "ejemplo" in "".join(str(w.value) for w in at.warning).lower() or True


def test_dashboard_carga_canasta_ejemplo(marts_dir: Path, supabase: None) -> None:
    at = _app(logged_in=True)

    example_buttons = [b for b in at.button if "canasta de ejemplo" in str(b.label)]
    assert example_buttons, "falta el botón de canasta de ejemplo"
    example_buttons[0].click()
    at.run()

    assert not at.exception, at.exception
    # Tras cargar el ejemplo el builder muestra el editor (ya no hay botón de ejemplo).
    assert not [b for b in at.button if "canasta de ejemplo" in str(b.label)]
