# Decisiones de arquitectura (ADRs breves)

## ADR-001 — La fuente son 7 recursos rotativos, no un paquete por fecha

**Decisión:** resolver el recurso del día vía CKAN (`package_show`) usando la fecha de
`description`; particionar por esa fecha.

**Alternativa descartada:** construir URLs por fecha (`sepa_YYYY-MM-DD.zip`). No existen.

**Por qué:** la fuente publica `sepa_lunes.zip` … `sepa_domingo.zip` y los sobrescribe cada
semana. El nombre del día no identifica la fecha; la fecha real está en `description`.

**Consecuencia:** solo se pueden recuperar los últimos 7 días. El backfill máximo es 7 días.
El sensor debe comparar la fecha publicada con la esperada, no solo el día de la semana.

## ADR-002 — Alcance geográfico por defecto: `AR-C` + `AR-B`

**Decisión:** `SCOPE_PROVINCES=AR-C,AR-B`.

**Alternativa descartada:** "CABA + GBA" por lista de localidades. Requiere una lista
mantenida a mano y no está en la fuente como tal.

**Por qué:** `sucursales_provincia` usa ISO 3166-2. `AR-B` incluye toda la provincia de
Buenos Aires, no solo el GBA.

**Consecuencia:** se documenta que el alcance es más amplio que "GBA/AMBA". El alcance es
configurable por variable de entorno.

## ADR-003 — La ingesta calcula agregados y detalle tracked; no persiste el detalle completo

**Decisión:** escribir por día:
`agg_precio_ean_diario` (todos los EAN × provincia), `fct_precio_diario` (solo
`tracked_products` = canasta + top-N por cobertura), `sucursales`, `comercios`, `rejects`.

**Alternativa descartada:** persistir todas las filas de `productos.csv` normalizadas.

**Por qué:** el paquete diario tiene ~12 M de precios; el detalle completo no entra en la rama
`data` ni aporta a las 4 vistas del dashboard. La especificación ya pide dos niveles de detalle.

**Consecuencia:** `stg_sepa__productos` representa el detalle tracked, no todos los productos.
Se agrega `stg_sepa__agg_ean_provincia`. Documentado en `DATA_MODEL.md`.

## ADR-004 — Índice y ranking en Python testeable, no en SQL dbt

**Decisión:** dbt produce los insumos (`fct_precio_diario`,
`mart_canasta_item_cadena_diario`); un módulo Python puro calcula cobertura, carry-forward,
fecha base, índice y ahorro, con tests unitarios.

**Alternativa descartada:** toda la fórmula en modelos dbt.

**Por qué:** la especificación exige tests unitarios de la fórmula con cobertura parcial y
carry-forward. Es más claro y testeable en Python que en SQL.

**Consecuencia:** los marts `mart_indice_canasta` y `mart_ranking_cadenas` se materializan
desde un asset Dagster que usa ese módulo. dbt sigue siendo dueño de dims/fct/agg/costos.

## ADR-005 — La rama `data` publica solo marts livianos

**Decisión:** publicar índice, ranking, costo por cadena, detalle de canasta del día, catálogo
y salud de datos. Los crudos y agregados completos quedan efímeros con retención local
documentada.

**Alternativa descartada:** publicar 90 días de detalle/agregados completos en git.

**Por qué:** el dashboard debe cargar en segundos y la rama `data` no debe inflarse. Streamlit
Community Cloud tiene ~2,7 GB de RAM y hiberna a las 12 h sin tráfico.

**Consecuencia:** el histórico del índice se persiste en marts pequeños. Cambiar la canasta no
recalcula ítems que nunca estuvieron en el set tracked; se documenta en `LIMITATIONS.md`.

## ADR-006 — Licencia: citar CC BY 4.0 del dataset y registrar la discrepancia

**Decisión:** atribuir "Fuente: Secretaría de Comercio, Precios SEPA
(datos.produccion.gob.ar), CC BY 4.0".

**Por qué:** el metadato CKAN del dataset declara CC BY 4.0; los términos de
preciosclaros.gob.ar declaran CC BY 2.5 AR. Son fuentes oficiales en conflicto.

**Consecuencia:** la discrepancia queda visible en `SOURCES.md` y en `LIMITATIONS.md`.

## ADR-007 — Descarga por HTTP/1.1 y sin reanudación confiable

**Decisión:** descargar el ZIP completo a `./data/tmp`, con HTTP/1.1, reintentos y backoff;
procesar y borrar.

**Alternativa descartada:** descarga por rangos con reanudación.

**Por qué:** el servidor anuncia `accept-ranges`, pero responde 200 con el cuerpo completo a un
`Range`. Además se observó `FRAME_SIZE_ERROR` de HTTP/2 en una descarga.

**Consecuencia:** si la descarga se corta, se reintenta desde cero. El ZIP se descarga una vez
por día; el costo es aceptable (~320 MB).

## ADR-008 — Rutas de datos y temporales dentro de `./data`

**Decisión:** `DATA_DIR=./data`, `TMPDIR=./data/tmp`,
`duckdb temp_directory=./data/duckdb_tmp`. Nada pesado en `/tmp`.

**Por qué:** restricción explícita del entorno: `/tmp` puede ser RAM y el disco total debe
quedar por debajo de 50 GB.

**Consecuencia:** Makefile, scripts y Docker exportan `TMPDIR`. La ingesta borra crudos y
temporales en `finally`. Guard de disco libre mínimo 10 GB.

## ADR-009 — Versiones fijadas por `uv lock`

**Decisión:** Python 3.12, `uv.lock` commiteado. Si `duckdb 2.x` no es compatible con
`dbt-duckdb`, se fija `duckdb 1.5.x`.

**Por qué:** `dagster-dbt` acepta `dbt-core <1.13`; `dbt-duckdb` y `duckdb` deben resolver
juntos. Se valida con `dbt build` en CI.

**Consecuencia:** actualizar versiones requiere correr tests y `dbt build`.

## ADR-010 — Normalizar CSV malformados antes de DuckDB

**Decisión:** la ingesta normaliza cada CSV a filas lógicas de ancho fijo antes de cargarlo:
quita BOM, NUL y `\r`, une líneas de continuación que empiezan con `|`, rellena campos
faltantes con vacío y corta el footer de actualización. Los ZIP internos vacíos se saltean
con un warning.

**Por qué:** el origen real trae `\r\n` dentro de filas de `sucursales.csv`, líneas cortas,
NULs y footers con y sin tilde. El parser estricto de DuckDB rechaza esos casos. No se usa
`ignore_errors` para no perder filas en silencio.

**Consecuencia:** la carga es más lenta (~66 s para 1,5 GB) pero falla ruidosamente ante un
cambio de esquema o una fila con demasiados campos.

## ADR-011 — dbt lee Parquet externo y la canasta activa desde `basket_items.parquet`

**Decisión:** dbt-duckdb declara las salidas de la ingesta como `sources` externos con
`external_location` sobre `data/raw/<tabla>/fecha=*/*.parquet` (`hive_partitioning=true`).
La ingesta escribe además `data/raw/basket_items.parquet` desde `basket.yml` (o
`basket.example.yml` si no existe) para que dbt pueda calcular el costo por cadena.

**Alternativa descartada:** copiar los Parquet a tablas DuckDB en un paso previo.

**Por qué:** evita duplicar datos y mantiene una sola fuente de verdad; `dbt build` es
idempotente y se puede correr sobre fixtures cambiando `CANASTA_DATA_DIR`.

**Consecuencia:** los modelos dbt dependen de que exista `basket_items.parquet`; la ingesta
lo genera siempre, incluso vacío. Los marts de índice/ranking siguen en Python (ADR-004).

## ADR-012 — dbt corre con cwd `dbt/` y rutas relativas `../data`

**Decisión:** `DbtCliResource` y los targets del Makefile ejecutan dbt desde `dbt/`. Los
defaults de `profiles.yml` y `sources.yml` son `../data/canasta.duckdb` y `../data/raw`.

**Por qué:** Dagster lanza dbt con `cwd=dbt/`; con rutas relativas al repo los modelos
buscaban `dbt/data/...`. Las variables de entorno (`CANASTA_DATA_DIR`, `CANASTA_DB`,
`DUCKDB_TEMP_DIR`) siguen permitiendo apuntar a fixtures o a otra ruta absoluta.

**Consecuencia:** `make dbt` y `make dbt-fixtures` cambian de directorio antes de invocar dbt.
Si se corre `dbt` a mano, hacerlo desde `dbt/` o exportar las variables absolutas.

## ADR-013 — Ejecución dbt completa por partición, no incremental

**Decisión:** el asset dbt se materializa por partición, pero `dbt build` recorre todas las
fechas disponibles. Los modelos son tablas completas, no incrementales.

**Por qué:** v1 tiene una sola partición real y la simplicidad pesa más que el ahorro. La
selección por partición queda como `shortcut:` en `definitions.py`.

**Consecuencia:** un backfill de N días reconstruye los marts N veces. Si el histórico crece,
filtrar por `var('fecha')` en staging o pasar a modelos incrementales.

## ADR-014 — El dashboard lee solo marts, locales o desde la rama `data`

**Decisión:** `dashboard/app.py` lee `data/marts/*.parquet` si existen; si no, descarga el
mismo archivo desde `https://raw.githubusercontent.com/.../data/marts/`. La URL se puede
pisar con `CANASTA_DATA_URL`.

**Alternativa descartada:** consultar DuckDB o el Parquet crudo desde Streamlit.

**Por qué:** los marts pesan 24 KB, el deploy no necesita secretos ni base de datos y la
rama `data` queda como contrato público estable.

**Consecuencia:** si la rama `data` no existe o está vacía, el dashboard falla visiblemente.
Subir una canasta distinta no recalcula los marts en el navegador.

## ADR-015 — Docker Compose usa fixtures, no descarga SEPA

**Decisión:** la imagen corre `scripts/demo.sh`, que genera fixtures, ejecuta `dbt build`,
materializa marts y levanta Streamlit en `0.0.0.0:8501` con un volumen nombrado.

**Por qué:** `docker compose up` debe funcionar en una máquina limpia sin descargar 320 MB ni
depender de que la fuente esté publicada. El pipeline real se corre con `make ingest`/Dagster.

**Consecuencia:** el demo Docker muestra 2 EAN y 2 fechas de ejemplo; no es el índice real.
El volumen se descarta con `docker compose down -v`.

## ADR-016 — Marts genéricos por provincia para calcular cualquier canasta en la UI

**Decisión:** `canasta marts` publica además `mart_catalogo` (EANs tracked con descripción,
marca y cantidad de cadenas), `mart_precio_ean_diario` (fecha × provincia × EAN, mediana) y
`mart_precio_ean_cadena` (última fecha × provincia × cadena × EAN, mediana), todos con columna
`provincia`.

**Alternativa descartada:** marts por usuario o recálculo del pipeline por canasta; también
publicar los 122k EANs (solo hay agregado por provincia, sin desglose por cadena).

**Por qué:** el dashboard debe calcular el índice y el ranking de una canasta que el usuario
arma en el navegador, sin backend de cómputo. Los ~2.500 EANs tracked son los únicos con
precio por sucursal/cadena, y con columna `provincia` el usuario elige alcance dentro de lo
publicado.

**Consecuencia:** la canasta de la UI está limitada al catálogo tracked (un basket.yml con
EANs fuera del catálogo queda sin precio y baja la cobertura). Con varias provincias
seleccionadas el precio es mediana de medianas provinciales (`shortcut:` en
`dashboard/compute.py`). Los marts crecen ~5k filas/día.

## ADR-017 — Cuentas gestionadas por Supabase, canastas en Postgres con RLS

**Decisión:** registro y login con Supabase Auth (email + contraseña vía GoTrue REST, desde
el Python de Streamlit). La canasta se guarda en una tabla `baskets` de Supabase Postgres,
accedida por PostgREST con el JWT del usuario, con RLS `auth.uid() = user_id`. Credenciales
en `st.secrets` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`); nunca tocan el navegador ni el repo.
Esquema en `supabase/schema.sql`.

**Alternativa descartada:** auth propio (contraseñas, sesiones, reset) o anónimo por UUID en
localStorage; también un backend FastAPI separado.

**Por qué:** el usuario pidió persistencia server-side con cuentas. El Python de Streamlit
corre en el servidor, así que el anon key y el JWT nunca se exponen al navegador y la RLS
aisla usuarios entre sí sin código nuestro. Sin servicio extra que desplegar.

**Consecuencia:** dependencia externa (proyecto Supabase free tier) y un secreto nuevo; las
cuentas son obligatorias, así que sin `SUPABASE_URL`/`SUPABASE_ANON_KEY` el dashboard muestra
un error de configuración y no abre. La confirmación de email se deshabilita en v1; probar RLS
con dos usuarios antes de exponer el deploy. Un workflow semanal hace ping a Supabase para
que el free tier no pause el proyecto.

## ADR-018 — La canasta se arma en la UI y se calcula en sesión, no en el pipeline

**Decisión:** primera pestaña "Armá tu canasta": búsqueda en el catálogo, cantidades y
provincia; guardado en la cuenta (con alta de cuenta en el mismo flujo). Índice y ranking se
calculan en cada render reutilizando `canasta.index.build_index` y
`canasta.ranking.rank_chains` sobre los marts genéricos. `basket.yml` queda como canasta de
ejemplo y como formato de export/import.

**Alternativa descartada:** recomputar marts del pipeline por canasta subida (es el flujo v1
original, exige terminal y no escala a visitantes).

**Por qué:** elimina la barrera del .yml + terminal para usuarios no técnicos; el cómputo en
sesión es barato (marts de ~5k-100k filas) y no multiplica corridas del pipeline diario.

**Consecuencia:** la canasta siempre persiste en la cuenta (login obligatorio); el
export/import de `basket.yml` queda como respaldo y para migrar canastas. Al loguearse se
carga la canasta guardada y el resto de las vistas se calculan en sesión. Los marts
`mart_indice_canasta`, `mart_ranking_cadenas` y `mart_canasta_detalle` siguen publicándose
para docs/números, pero el dashboard ya no los lee.
