# Progreso del proyecto

Actualizado: 2026-11-10.

## Fase 7 — Canasta armada desde la UI

- [x] 3 marts genéricos con columna `provincia`: catálogo, precio por fecha×provincia×EAN y
      precio por provincia×cadena×EAN de la última fecha (`canasta marts`).
- [x] Pestaña "Armá tu canasta": búsqueda en catálogo, cantidades, selector de provincia,
      export/import de `basket.yml` y carga de la canasta de ejemplo.
- [x] Índice y ranking calculados en sesión reutilizando `canasta.index`/`canasta.ranking`.
- [x] Cuentas obligatorias vía Supabase (GoTrue REST) y canasta por usuario en Postgres con
      RLS (`supabase/schema.sql`); sin configuración el dashboard muestra un error y no abre.
- [x] Poda de retención (`canasta prune`: 90 días de detalle, 365 de agregados) y cache de
      `data/raw` en el workflow diario para que la historia del índice se acumule.
- [x] Workflow semanal `supabase-ping` para que el free tier no pause el proyecto.
- [x] Tests: writer de marts genéricos, compute, builder, store (httpx mockeado), poda y
      smoke del dashboard con `streamlit.testing.v1.AppTest` (45 tests).
- [x] Verificación end-to-end con fixtures: dbt build (33 nodos) + marts (7 archivos) +
      Streamlit HTTP 200 sin excepciones.
- [ ] Probar RLS con dos usuarios reales y deshabilitar confirmación de email en Supabase.

## Fase 0 — Verificar fuente y formato

- [x] Localizar URL de descarga vigente y API de metadatos.
- [x] Verificar patrón de nombres, hora de publicación y recursos disponibles.
- [x] Verificar licencia declarada y discrepancia entre fuentes.
- [x] Documentar diccionario de columnas real (Anexo II).
- [x] Descargar un paquete real y describir estructura interna.
- [x] Medir tamaño comprimido/descomprimido, filas y tiempos.
- [x] Documentar decisión de volumen.

## Fase 1 — Ingesta → Parquet particionado

- [x] Descarga idempotente por fecha.
- [x] Esquema explícito y fallo ante cambio de columnas.
- [x] Filtro de alcance y validación EAN con rechazos.
- [x] Escritura atómica de la partición.
- [x] Reejecución no duplica filas (mismos conteos en dos corridas).
- [x] Memoria y disco acotados, medidos.
- [x] Crudos y temporales borrados tras procesar.

## Fase 2 — Modelos dbt + tests

- [x] Staging, intermediate y marts.
- [x] Tests de claves, precios, EAN y relaciones.
- [x] `dbt build` verde sobre fixtures (`make dbt-fixtures`, 33 nodos).
- [x] `dbt build` verde sobre un día real (`make dbt`, 33 nodos, 2,6 s).

## Fase 3 — Dagster

- [x] Assets particionados por fecha (`sepa_raw_parquet`).
- [x] Assets dbt integrados (`dagster-dbt`, 12 assets).
- [x] Asset checks de volumen, precio y rechazos.
- [x] Schedule diario (`daily_sepa`, 16:30 UTC).
- [x] Sensor de publicación con reintentos cada 30 min; a los 8 intentos loguea `FALLO_FUENTE`.
- [x] Materialización por CLI (dbt asset verificado); UI pendiente de prueba manual.

## Fase 4 — Índice y ranking

- [x] Fórmula base 100 con cobertura y fecha base.
- [x] Carry-forward máximo 3 días e incompletos.
- [x] Ranking de cadenas y ahorro con/sin restricción de cadena.
- [x] Tests unitarios de casos parciales y borde (6 tests).
- [x] `basket.example.yml` generado desde EANs reales.
- [x] `canasta marts` escribe índice, ranking, detalle y salud.

## Fase 5 — Dashboard y publicación

- [x] 4 vistas Streamlit: canasta, índice, dónde comprar y salud.
- [x] Lee solo marts livianos (`data/marts/*.parquet` o rama `data` por URL).
- [x] Publicación de marts a la rama `data` (`make publish-data` + workflow diario).
- [ ] CI verde (workflow creado; requiere push y primera corrida en GitHub).
- [x] Demo local con datos de ejemplo (Streamlit local y `docker compose up`).
- [ ] Deploy público (bloqueado por OAuth humano, ver `BLOCKERS.md`).

## Fase 6 — Docs y números medidos

- [x] README en inglés con resumen de 3 líneas en español.
- [x] ARCHITECTURE, DATA_MODEL, LIMITATIONS.
- [x] Números medidos con fecha y comando.
- [ ] Checklist 1.6 completo (faltan CI verde, corrida programada real y demo público).

## Mediciones Fase 0

| Métrica | Valor | Comando / fuente |
|---|---|---|
| ZIP comprimido | 319.893.305 bytes (metadato CKAN) | `package_show` |
| ZIP descargado | 319.893.305 bytes (coincide con CKAN) | `curl --http1.1` + `zipfile.testzip()` |
| ZIP descomprimido | 1.533 GB de CSV (18 ZIPs anidados, 1 vacío) | suma de `ZipInfo.file_size` |
| Filas `productos` | 14.381.167 | `meta.json` |
| Filas `sucursales` | 3.021 | `meta.json` |
| Filas `comercios` | 30 | `meta.json` |
| Tiempo de descarga | ~6 min (servidor intermitente) | `curl` 2026-11-03 |
| Tiempo de ingesta | 212 s (load 66 s, transform 142 s, write 5 s) | `canasta ingest` |
| RSS pico | 3.973.004 KB (~3,97 GB) | `/usr/bin/time -v` |
| Disco pico | ~1,4 GB temporales + 320 MB ZIP | `du -sh data` |
| Parquet generado | 6,6 MB (122.444 filas agg + 3.335.869 fct) | `du -sh data/raw` |

## Mediciones Fase 2

| Métrica | Valor | Comando |
|---|---|---|
| Nodos dbt | 33 (5 staging/intermediate views, 6 marts tables, 22 tests) | `dbt build` |
| `dbt build` real | PASS=33, 2,6 s | `make dbt` |
| `dim_producto` | 2.500 filas | `main_marts.dim_producto` |
| `dim_sucursal` | 2.122 filas | `main_marts.dim_sucursal` |
| `fct_precio_diario` | 3.335.869 filas | `main_marts.fct_precio_diario` |
| `agg_precio_ean_diario` | 122.444 filas | `main_marts.agg_precio_ean_diario` |
| `mart_canasta_costo_diario` | 21 cadenas para 2026-11-03 | `main_marts.mart_canasta_costo_diario` |
| Fixtures dbt | 2 fechas, 3 cadenas, 2 EAN, 33 nodos verdes | `make dbt-fixtures` |

## Mediciones Fase 3

| Métrica | Valor | Comando |
|---|---|---|
| Assets Dagster | 2 definiciones (1 ingesta + 1 grupo dbt con 12 assets) | `dagster definitions validate` |
| Asset checks | 3 (volumen, precio, rechazos) | `dagster definitions validate` |
| Materialización CLI dbt | PASS=8 (modelo + tests de `fct_precio_diario`) | `dagster asset materialize ...` |
| Check volumen | 14.381.167 `productos_raw`, sin histórico | ejecución directa |
| Check precio | 3.335.869 filas, 0 no positivos, 41 outliers (0,0012%) | ejecución directa |
| Check rechazos | 324.216 rechazos (2,25% de productos crudos) | ejecución directa |

## Mediciones Fase 4

| Métrica | Valor | Comando |
|---|---|---|
| Índice 2026-11-03 | 100,00 (primera fecha, cobertura 100%) | `canasta marts` |
| Costo canasta (mediana alcance) | ARS 157.770,98 | `mart_indice_canasta` |
| Ranking | 21 cadenas; mejor `Maxi` ARS 141.888 | `mart_ranking_cadenas` |
| Ahorro potencial | ARS 20.061 comprando ítem por ítem | `mart_ranking_cadenas` |
| Detalle por cadena × producto | 301 filas | `mart_canasta_detalle` |
| Tests fórmula | 6 (base, carry-forward, parcial, borde) | `pytest` |

## Mediciones Fase 5

| Métrica | Valor | Comando |
|---|---|---|
| Vistas dashboard | 4 | `dashboard/app.py` |
| Tamaño marts | 24 KB (4 Parquet) | `du -sh data/marts` |
| Streamlit local | HTTP 200, sin excepciones | `streamlit run dashboard/app.py` |
| Docker demo | imagen 1,57 GB; HTTP 200 en 8501 | `docker compose up --build` |
| Fixtures Docker | PASS=33; marts: 2 índice, 2 ranking, 4 detalle, 1 salud | logs del contenedor |
| CI | workflow `ci.yml` creado; sin ejecutar | pendiente de push |
| Workflow diario | `daily.yml` creado; cron 17:30 UTC | pendiente de push |

## Checklist 1.6

- [x] `make setup && make test` pasa en una máquina limpia (verificado local).
- [x] `docker compose up` levanta el dashboard con datos de ejemplo (fixtures).
- [ ] CI verde.
- [ ] Pipeline programado ejecutándose al menos una vez en producción gratuita.
- [ ] Demo público accesible o capturas + instrucciones (bloqueado por OAuth).
- [x] `docs/` completos, README según 1.4, números medidos.
- [x] Sin secretos en el historial (gitleaks en pre-commit; repo sin commits todavía).
