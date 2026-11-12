"""Tests del store de canastas contra Supabase PostgREST mockeado."""

from __future__ import annotations

import json

import httpx
import pytest
import streamlit as st

from canasta.basket import BasketItem
from dashboard import store


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> dict:
    saved: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/v1/baskets":
            if request.method == "POST":
                saved["payload"] = json.loads(request.content)
                saved["prefer"] = request.headers.get("prefer")
                return httpx.Response(201)
            if "payload" not in saved:
                return httpx.Response(200, json=[])
            return httpx.Response(
                200,
                json=[
                    {
                        "items": saved["payload"]["items"],
                        "provincias": saved["payload"]["provincias"],
                    }
                ],
            )
        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)

    def fake(method: str):
        def call(url: str, headers=None, json=None, timeout=None):
            return transport.handle_request(httpx.Request(method, url, headers=headers, json=json))

        return call

    monkeypatch.setattr(store.httpx, "post", fake("POST"))
    monkeypatch.setattr(store.httpx, "get", fake("GET"))
    return saved


def test_save_y_load_roundtrip(mock_http: dict) -> None:
    st.session_state["sb_token"] = "tok"
    items = [BasketItem(ean="7790000000010", label="Leche 1 L", qty_per_month=8.0)]

    store.save_basket("https://sb.local", "anon", items, ["AR-C"])

    assert mock_http["prefer"] == "resolution=merge-duplicates"
    assert mock_http["payload"] == {
        "items": [{"ean": "7790000000010", "label": "Leche 1 L", "qty_per_month": 8.0}],
        "provincias": ["AR-C"],
    }

    loaded = store.load_basket("https://sb.local", "anon")
    assert loaded is not None
    assert loaded[0] == items
    assert loaded[1] == ("AR-C",)


def test_load_sin_canasta_guardada(mock_http: dict) -> None:
    st.session_state["sb_token"] = "tok"

    assert store.load_basket("https://sb.local", "anon") is None
