"""Dashboard Streamlit: armá tu canasta, índice, ranking y salud de los datos."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from canasta.basket import BasketItem, active_basket_path, load_basket  # noqa: E402
from dashboard import auth, builder, compute, store  # noqa: E402

st.set_page_config(page_title="Canasta personal", page_icon="C", layout="wide")

MARTS_DIR = Path(os.getenv("CANASTA_MARTS_DIR", str(ROOT / "data" / "marts")))
DATA_URL = os.getenv(
    "CANASTA_DATA_URL",
    "https://raw.githubusercontent.com/juanmas-hub/canasta-personal/data/marts",
)


@st.cache_data(ttl=3600)
def load_mart(name: str) -> pd.DataFrame:
    local = MARTS_DIR / f"{name}.parquet"
    if local.exists():
        return pd.read_parquet(local)
    response = httpx.get(f"{DATA_URL}/{name}.parquet", timeout=30, follow_redirects=True)
    response.raise_for_status()
    return pd.read_parquet(io.BytesIO(response.content))


def money(value: float | None) -> str:
    return "-" if value is None else f"${value:,.0f}"


def init_state() -> None:
    if "items" not in st.session_state:
        st.session_state["items"] = []
    if "provincias" not in st.session_state:
        st.session_state["provincias"] = []
    if "loaded_db" not in st.session_state:
        st.session_state["loaded_db"] = False


st.sidebar.title("Canasta personal")
config = auth.sb_config()
init_state()

if config is None:
    st.title("Canasta personal")
    st.error(
        "Faltan SUPABASE_URL y SUPABASE_ANON_KEY en los secrets de esta app. "
        "Sin cuentas configuradas no se puede entrar."
    )
    st.stop()

if not auth.logged_in():
    st.title("Canasta personal")
    st.caption("Entrá con tu cuenta para armar y guardar tu canasta.")
    gate_login, gate_signup = st.tabs(["Ingresar", "Crear cuenta"])
    with gate_login:
        auth.login_form(config[0], config[1], "sb_gate_login")
    with gate_signup:
        auth.signup_form(config[0], config[1], "sb_gate_signup")
    st.stop()

if not st.session_state["loaded_db"]:
    try:
        saved = store.load_basket(config[0], config[1])
    except Exception as exc:
        st.sidebar.error(f"No pude leer tu canasta guardada: {exc}")
        saved = None
    if saved is not None:
        st.session_state["items"], st.session_state["provincias"] = saved
    st.session_state["loaded_db"] = True

auth.auth_ui(config)

try:
    catalog = load_mart("mart_catalogo")
    precio_diario = load_mart("mart_precio_ean_diario")
    precio_cadena = load_mart("mart_precio_ean_cadena")
    salud = load_mart("mart_salud")
except Exception as exc:
    st.error(f"No pude leer los marts: {exc}")
    st.stop()

items = st.session_state["items"]
using_example = not items
if using_example:
    items = list(load_basket(active_basket_path()).items)

provincias_disponibles = sorted(precio_diario["provincia"].dropna().unique())
provincias = st.session_state["provincias"] or provincias_disponibles

st.sidebar.caption(f"{len(items)} productos · alcance {', '.join(provincias) or 'sin definir'}")
st.sidebar.info(
    "Los precios son los que cada cadena informa al SEPA, no una foto de góndola. "
    "El índice es propio: no es inflación oficial ni IPC."
)

st.title("Canasta personal")
st.caption("Armá tu canasta, seguí su índice base 100 y compará cadenas con datos públicos SEPA.")

armar_tab, canasta_tab, indice_tab, comprar_tab, salud_tab = st.tabs(
    ["Armá tu canasta", "Canasta", "Índice", "Dónde comprar hoy", "Salud de los datos"]
)

with armar_tab:
    st.subheader("Armá tu canasta")
    st.caption(
        "Buscá productos del catálogo (~2.500 con mejor cobertura de precio), poné cuántas "
        "unidades por mes comprás y elegí provincia. Todo lo demás se recalcula al instante."
    )

    provincias_elegidas = st.multiselect(
        "Provincias del alcance",
        options=provincias_disponibles,
        default=[p for p in st.session_state["provincias"] if p in provincias_disponibles]
        or list(provincias_disponibles),
    )
    st.session_state["provincias"] = provincias_elegidas
    provincias = provincias_elegidas or provincias_disponibles

    if st.session_state["items"]:
        current = pd.DataFrame(
            [
                {"ean": item.ean, "producto": item.label, "unidades/mes": item.qty_per_month}
                for item in st.session_state["items"]
            ]
        )
        st.markdown(f"**Tu canasta ({len(current)} productos)**")
        edited = st.data_editor(
            current,
            key="basket_editor",
            width="stretch",
            hide_index=True,
            disabled=["ean", "producto"],
        )
        col_apply, col_export = st.columns(2)
        if col_apply.button("Aplicar cambios"):
            st.session_state["items"] = [
                BasketItem(
                    ean=str(row["ean"]),
                    label=str(row["producto"]),
                    qty_per_month=float(row["unidades/mes"]),
                )
                for _, row in edited.iterrows()
                if row["unidades/mes"] > 0
            ]
            st.rerun()
        yaml_text = builder.basket_yaml(st.session_state["items"], provincias_elegidas)
        col_export.download_button(
            "Descargar basket.yml",
            data=yaml_text,
            file_name="basket.yml",
            mime="text/yaml",
        )
    else:
        st.info(
            "Tu canasta está vacía: buscá productos abajo o cargá la canasta de ejemplo. "
            "Sin canasta propia, el resto de las vistas muestra la canasta de ejemplo."
        )
        if st.button("Cargar canasta de ejemplo"):
            st.session_state["items"] = list(load_basket(active_basket_path()).items)
            st.rerun()

    st.markdown("**Buscar productos**")
    query = st.text_input(
        "Nombre o marca (ej: leche, yerba, serenisima)", key="search_query", value=""
    )
    results = builder.search_catalog(catalog, query)
    if results.empty:
        st.warning("No hay productos que coincidan con la búsqueda.")
    else:
        st.caption(f"{len(results)} resultados (mostrando hasta 50). Poné unidades/mes y agregá.")
        addable = results.assign(cantidad=0.0)[
            ["descripcion", "marca", "presentacion", "n_cadenas", "ean", "cantidad"]
        ]
        addable = addable.rename(columns={"descripcion": "producto"})
        edited_add = st.data_editor(
            addable,
            key="search_editor",
            width="stretch",
            hide_index=True,
            disabled=["producto", "marca", "presentacion", "n_cadenas", "ean"],
        )
        if st.button("Agregar a la canasta"):
            by_ean = {item.ean: item for item in st.session_state["items"]}
            for _, row in edited_add[edited_add["cantidad"] > 0].iterrows():
                ean = str(row["ean"])
                qty = float(row["cantidad"])
                if ean in by_ean:
                    current_item = by_ean[ean]
                    by_ean[ean] = BasketItem(
                        ean=ean,
                        label=current_item.label,
                        qty_per_month=current_item.qty_per_month + qty,
                    )
                else:
                    by_ean[ean] = BasketItem(
                        ean=ean,
                        label=builder.item_label(
                            row["producto"], row["marca"], row["presentacion"]
                        ),
                        qty_per_month=qty,
                    )
            st.session_state["items"] = list(by_ean.values())
            st.rerun()

    uploaded = st.file_uploader("O subí un basket.yml", type=["yml", "yaml"])
    if uploaded is not None:
        try:
            basket = builder.parse_basket_upload(uploaded.getvalue())
        except Exception as exc:
            st.error(f"No se pudo leer la canasta: {exc}")
        else:
            if basket.items:
                st.session_state["items"] = list(basket.items)
                st.session_state["provincias"] = list(basket.provincias)
                st.success(f"Canasta cargada: {len(basket.items)} productos.")
                st.rerun()

    st.markdown("---")
    if st.button("Guardar mi canasta", type="primary", disabled=not st.session_state["items"]):
        try:
            store.save_basket(config[0], config[1], st.session_state["items"], provincias_elegidas)
        except Exception as exc:
            st.error(f"No pude guardar la canasta: {exc}")
        else:
            st.success("Canasta guardada en tu cuenta.")

with canasta_tab:
    st.subheader("Tu canasta")
    if using_example:
        st.warning("Mostrando la canasta de ejemplo; armá la tuya en la primer pestaña.")
    precios = compute.last_daily_prices(precio_diario, provincias)
    rows = [
        {
            "producto": item.label,
            "ean": item.ean,
            "unidades/mes": item.qty_per_month,
            "precio": precios.get(item.ean),
            "costo": (item.qty_per_month * precios[item.ean] if item.ean in precios else None),
        }
        for item in items
    ]
    frame = pd.DataFrame(rows)
    st.dataframe(frame, width="stretch", hide_index=True)
    with_precio = frame.dropna(subset=["precio"])
    st.caption(
        f"Total: {frame['unidades/mes'].sum():,.0f} unidades/mes · "
        f"Costo estimado: {money(with_precio['costo'].sum() if not with_precio.empty else None)} · "
        f"{len(with_precio)}/{len(frame)} productos con precio. "
        "El precio es la mediana entre sucursales del alcance."
    )

with indice_tab:
    result = compute.compute_index(precio_diario, items, provincias)
    frame = compute.index_frame(result)
    if frame.empty:
        st.warning("Todavía no hay fechas para el alcance elegido.")
    else:
        latest = frame.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Índice", "-" if pd.isna(latest["indice"]) else f"{latest['indice']:.2f}")
        col2.metric("Costo canasta", money(latest["costo"]))
        col3.metric("Cobertura", f"{latest['cobertura']:.1f}%")
        col4.metric("Base", str(result.base_fecha or "sin base"))

        chart = frame.dropna(subset=["indice"])
        if chart.empty:
            st.warning("Todavía no hay una fecha con cobertura suficiente para fijar la base.")
        else:
            fig = px.line(
                chart,
                x="fecha",
                y="indice",
                markers=True,
                labels={"fecha": "Fecha", "indice": "Índice base 100"},
            )
            incomplete = chart[~chart["completo"]]
            if not incomplete.empty:
                fig.add_scatter(
                    x=incomplete["fecha"],
                    y=incomplete["indice"],
                    mode="markers",
                    marker={"color": "red", "size": 12},
                    name="incompleto",
                )
            st.plotly_chart(fig, width="stretch")
            if len(chart) == 1:
                st.info(
                    "Hay una sola fecha publicada; el índice empieza a tener serie con más días."
                )

        st.dataframe(frame.sort_values("fecha", ascending=False), width="stretch", hide_index=True)

with comprar_tab:
    result = compute.compute_ranking(precio_cadena, items, provincias)
    frame = compute.ranking_frame(result)
    complete = frame[frame["completo"]].sort_values("costo")
    if complete.empty:
        st.warning("Ninguna cadena cubre al menos el 90% de la canasta en la última fecha.")
    else:
        best = complete.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Mejor cadena", str(best["cadena"]))
        col2.metric("Costo una cadena", money(best["costo"]))
        col3.metric("Comprando por ítem", money(result.costo_surtido))
        col4.metric("Ahorro potencial", money(result.ahorro_potencial))
        fig = px.bar(
            complete,
            x="costo",
            y="cadena",
            orientation="h",
            labels={"costo": "Costo mensual", "cadena": ""},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
        st.dataframe(frame, width="stretch", hide_index=True)

    st.subheader("Detalle por producto")
    detail = compute.detail_frame(precio_cadena, items, provincias)
    chains = sorted(detail["cadena"].dropna().unique())
    if chains:
        chain = st.selectbox("Cadena", chains)
        st.dataframe(
            detail[detail["cadena"] == chain][["label", "ean", "qty_per_month", "precio", "costo"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No hay detalle de productos para la última fecha.")

with salud_tab:
    row = salud.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Última fecha", str(row["fecha"]))
    col2.metric("Productos crudos", f"{int(row['productos_raw']):,}")
    col3.metric("Rechazos", f"{int(row['rechazos']):,}")
    col4.metric("Cobertura canasta ejemplo", f"{row['cobertura_canasta']:.1f}%")
    st.dataframe(salud, width="stretch", hide_index=True)
    st.caption(
        "Fuente: Secretaría de Comercio, Precios SEPA (datos.produccion.gob.ar), CC BY 4.0. "
        "Los rechazos incluyen EAN internos, EAN inválidos y sucursales fuera de alcance."
    )
