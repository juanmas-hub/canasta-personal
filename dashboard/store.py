"""Canasta del usuario en Supabase Postgres (PostgREST) con RLS por auth.uid()."""

from __future__ import annotations

from collections.abc import Sequence

import httpx
import streamlit as st

from canasta.basket import BasketItem
from dashboard import auth

TIMEOUT = 15.0


def _headers(key: str, token: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _raise(r: httpx.Response) -> None:
    if r.is_success:
        return
    try:
        body = r.json()
        detail = body.get("message") or body.get("msg") or r.text
    except Exception:
        detail = r.text
    raise ValueError(f"Supabase: {detail or r.status_code}")


def _token(url: str, key: str, response: httpx.Response) -> str:
    """Retry de 401 renovando el access token una sola vez."""
    if response.status_code != 401:
        return str(st.session_state["sb_token"])
    token = auth.refresh_session(url, key)
    st.session_state["sb_token"] = token
    return token


def save_basket(
    url: str,
    key: str,
    items: Sequence[BasketItem],
    provincias: Sequence[str],
) -> None:
    token = str(st.session_state["sb_token"])
    payload = {
        "items": [
            {"ean": item.ean, "label": item.label, "qty_per_month": item.qty_per_month}
            for item in items
        ],
        "provincias": list(provincias),
    }
    response = httpx.post(
        f"{url}/rest/v1/baskets?on_conflict=user_id",
        headers={**_headers(key, token), "Prefer": "resolution=merge-duplicates"},
        json=payload,
        timeout=TIMEOUT,
    )
    if response.status_code == 401:
        token = _token(url, key, response)
        response = httpx.post(
            f"{url}/rest/v1/baskets?on_conflict=user_id",
            headers={**_headers(key, token), "Prefer": "resolution=merge-duplicates"},
            json=payload,
            timeout=TIMEOUT,
        )
    _raise(response)


def load_basket(url: str, key: str) -> tuple[list[BasketItem], tuple[str, ...]] | None:
    token = str(st.session_state["sb_token"])
    response = httpx.get(
        f"{url}/rest/v1/baskets?select=items,provincias",
        headers=_headers(key, token),
        timeout=TIMEOUT,
    )
    if response.status_code == 401:
        token = _token(url, key, response)
        response = httpx.get(
            f"{url}/rest/v1/baskets?select=items,provincias",
            headers=_headers(key, token),
            timeout=TIMEOUT,
        )
    _raise(response)
    rows = response.json()
    if not rows:
        return None
    items = [
        BasketItem(
            ean=str(entry["ean"]),
            label=str(entry.get("label") or entry["ean"]),
            qty_per_month=float(entry["qty_per_month"]),
        )
        for entry in rows[0]["items"]
    ]
    return items, tuple(str(p) for p in rows[0].get("provincias") or ())
