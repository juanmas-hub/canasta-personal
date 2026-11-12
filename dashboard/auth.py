"""Cuentas vía Supabase Auth (GoTrue REST). Las contraseñas nunca pasan por este código."""

from __future__ import annotations

import os
from collections.abc import Callable

import httpx
import streamlit as st

TIMEOUT = 15.0


def sb_config() -> tuple[str, str] | None:
    """URL y anon key de Supabase desde st.secrets o el entorno; None si no está configurado."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    try:
        url = url or st.secrets.get("SUPABASE_URL", "")
        key = key or st.secrets.get("SUPABASE_ANON_KEY", "")
    except Exception:
        pass
    if url and key:
        return url.rstrip("/"), key
    return None


def logged_in() -> bool:
    return bool(st.session_state.get("sb_token"))


def logout() -> None:
    for name in ("sb_token", "sb_refresh", "sb_user_id", "sb_email"):
        st.session_state.pop(name, None)


def _headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _raise(r: httpx.Response) -> None:
    if r.is_success:
        return
    try:
        body = r.json()
        detail = body.get("msg") or body.get("error_description") or r.text
    except Exception:
        detail = r.text
    raise ValueError(f"Supabase: {detail or r.status_code}")


def _store_session(session: dict) -> None:
    user = session.get("user") or {}
    st.session_state["sb_token"] = session["access_token"]
    st.session_state["sb_refresh"] = session.get("refresh_token")
    st.session_state["sb_user_id"] = user.get("id")
    st.session_state["sb_email"] = user.get("email")


def login(url: str, key: str, email: str, password: str) -> None:
    r = httpx.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers=_headers(key),
        json={"email": email, "password": password},
        timeout=TIMEOUT,
    )
    _raise(r)
    _store_session(r.json())


def signup(url: str, key: str, email: str, password: str) -> bool:
    """True si quedó logueado; False si el proyecto exige confirmación de email."""
    r = httpx.post(
        f"{url}/auth/v1/signup",
        headers=_headers(key),
        json={"email": email, "password": password},
        timeout=TIMEOUT,
    )
    _raise(r)
    session = r.json().get("session")
    if session:
        _store_session(session)
        return True
    return False


def refresh_session(url: str, key: str) -> str:
    """Renueva el access token vencido; levanta excepción si la sesión murió."""
    r = httpx.post(
        f"{url}/auth/v1/token?grant_type=refresh_token",
        headers=_headers(key),
        json={"refresh_token": st.session_state.get("sb_refresh")},
        timeout=TIMEOUT,
    )
    _raise(r)
    session = r.json()
    _store_session(session)
    return str(session["access_token"])


def login_form(
    url: str, key: str, prefix: str, on_success: Callable[[], None] | None = None
) -> None:
    email = st.text_input("Email", key=f"{prefix}_email")
    password = st.text_input("Contraseña", type="password", key=f"{prefix}_pass")
    if st.button("Ingresar", key=f"{prefix}_btn", type="primary"):
        try:
            login(url, key, email, password)
        except Exception as exc:
            st.error(str(exc))
        else:
            if on_success is not None:
                on_success()
            st.rerun()


def signup_form(
    url: str, key: str, prefix: str, on_success: Callable[[], None] | None = None
) -> None:
    email = st.text_input("Email", key=f"{prefix}_email")
    password = st.text_input("Contraseña", type="password", key=f"{prefix}_pass")
    if st.button("Crear cuenta", key=f"{prefix}_btn", type="primary"):
        try:
            ok = signup(url, key, email, password)
        except Exception as exc:
            st.error(str(exc))
        else:
            if ok:
                if on_success is not None:
                    on_success()
                st.rerun()
            else:
                st.info("Revisá tu email para confirmar la cuenta antes de ingresar.")


def auth_ui(config: tuple[str, str]) -> None:
    st.sidebar.success(f"Sesión: {st.session_state.get('sb_email')}")
    if st.sidebar.button("Cerrar sesión"):
        logout()
        st.session_state["items"] = []
        st.session_state["provincias"] = []
        st.session_state["loaded_db"] = False
        st.rerun()
