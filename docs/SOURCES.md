# Fuentes de datos — verificación Fase 0

Fecha de verificación: **2026-11-03** (UTC). Verificado por el agente contra la fuente real.

## 1. Fuente principal

| Campo | Valor verificado |
|---|---|
| Nombre | Precios Claros — Base SEPA (minoristas) |
| Publicador | Subsecretaría de Defensa del Consumidor y Lealtad Comercial, Ministerio de Economía |
| Portal | https://datos.produccion.gob.ar/dataset/sepa-precios |
| API CKAN | https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios |
| Frecuencia declarada | Diariamente |
| Hora real de publicación | ~16:19–16:20 UTC (13:19–13:20 America/Argentina/Buenos_Aires) |
| Licencia declarada en el dataset | Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/) |
| Licencia en preciosclaros.gob.ar | Creative Commons Atribución 2.5 Argentina (https://creativecommons.org/licenses/by/2.5/ar/legalcode) |
| Contacto de la fuente | soportesepa@comercio.gob.ar |
| Términos | https://www.preciosclaros.gob.ar/terminos_y_condiciones.html |

**Discrepancia de licencia:** el metadato del dataset dice CC BY 4.0; los términos del sitio
preciosclaros.gob.ar dicen CC BY 2.5 AR. Este proyecto cita el metadato del dataset (CC BY 4.0)
y deja constancia de la discrepancia. Atribución usada en README y dashboard:
"Fuente: Secretaría de Comercio, Precios SEPA (datos.produccion.gob.ar), CC BY 4.0".

## 2. Recursos publicados (medidos el 2026-11-03)

El dataset **no** publica un paquete por fecha con URL inmutable. Publica **siete recursos ZIP
rotativos**, uno por día de la semana, que se sobrescriben semanalmente. La fecha real del
contenido está en el campo `description` de cada recurso.

| Recurso | Fecha del contenido | `last_modified` (UTC) | Bytes |
|---|---|---|---|
| `sepa_lunes.zip` | 2026-11-02 | 2026-11-02T16:19:31Z | 324.136.705 |
| `sepa_martes.zip` | 2026-11-03 | 2026-11-03T16:19:20Z | 319.893.305 |
| `sepa_miercoles.zip` | 2026-10-28 | 2026-10-28T16:20:07Z | 321.862.263 |
| `sepa_jueves.zip` | 2026-10-29 | 2026-10-29T16:19:52Z | 324.924.535 |
| `sepa_viernes.zip` | 2026-10-30 | 2026-10-30T16:20:22Z | 324.628.542 |
| `sepa_sabado.zip` | 2026-10-31 | 2026-10-31T16:19:32Z | 325.191.281 |
| `sepa_domingo.zip` | 2026-11-01 | 2026-11-01T16:19:36Z | 323.611.021 |

Consecuencias:

- Solo están disponibles los **últimos 7 días**. No hay archivo histórico arbitrario.
- El backfill máximo posible es de 7 días.
- Para ingerir un día hay que resolver el recurso por la fecha de `description`, no por el
  nombre del día de la semana.
- El tamaño real es **~320 MB comprimidos por día**, no ~4 GB.

## 3. Comportamiento HTTP

- `HEAD` responde 200 con `content-range: bytes 0-<n>/<n>` y `last-modified`.
- La respuesta anuncia `accept-ranges: bytes`, pero un pedido `Range: bytes=0-1023` devolvió
  **HTTP 200 con el cuerpo completo**, no 206. La reanudación por rangos no es confiable.
- Velocidad observada desde la red de desarrollo: ~2–3 MB/s.
- Se debe usar un `User-Agent` identificable, timeout, reintentos con backoff y jitter.

## 4. Formato del paquete (Anexo II, Res. 678/2020)

Documento oficial: `anexo_6201340_2.pdf`, disponible como recurso del dataset.

- ZIP con **tres archivos CSV por comercio**: `comercio.csv`, `sucursales.csv`, `productos.csv`.
- Texto delimitado por **pipe (`|`)**, codificación **UTF-8**, fin de línea **CRLF**.
- La primera línea de cada archivo es el encabezado con los nombres de campo exactos.
- Los valores pueden venir entre comillas dobles si contienen pipe o comillas.
- Después de la última fila de datos hay una **línea en blanco** y una línea
  `Última actualización: YYYY-MM-DDTHH:MM:SS-03:00`. Esa línea no es un dato y debe descartarse.

### 4.1 `comercio.csv`

`id_comercio`, `id_bandera`, `comercio_cuit`, `comercio_razon_social`,
`comercio_bandera_nombre`, `comercio_bandera_url`, `comercio_ultima_actualizacion`,
`comercio_version_sepa`.

### 4.2 `sucursales.csv`

`id_comercio`, `id_bandera`, `id_sucursal`, `sucursales_nombre`, `sucursales_tipo`,
`sucursales_calle`, `sucursales_numero`, `sucursales_latitud`, `sucursales_longitud`,
`sucursales_observaciones`, `sucursales_barrio`, `sucursales_codigo_postal`,
`sucursales_localidad`, `sucursales_provincia`, más siete campos de horario
(`sucursales_<dia>_horario_atencion`).

`sucursales_provincia` usa **ISO 3166-2** (ej. `AR-C` = CABA, `AR-B` = Buenos Aires).

### 4.3 `productos.csv`

`id_comercio`, `id_bandera`, `id_sucursal`, `id_producto`, `productos_ean`,
`productos_descripcion`, `productos_cantidad_presentacion`,
`productos_unidad_medida_presentacion`, `productos_marca`, `productos_precio_lista`,
`productos_precio_referencia`, `productos_cantidad_referencia`,
`productos_unidad_medida_referencia`, `productos_precio_unitario_promo1`,
`productos_leyenda_promo1`, `productos_precio_unitario_promo2`,
`productos_leyenda_promo2`.

Notas:

- `id_producto` tiene 13 dígitos. Puede ser GTIN-8/13, UPC-A o un código interno.
- `productos_ean = 1` indica GTIN real; `0` indica código interno del comercio.
- `productos_precio_lista` es el precio base (sin descuentos).
- Los campos de promoción existen y son opcionales. No se usan en el índice base.

## 5. Inspección del paquete real

Se descargó un paquete real para medir estructura, filas, tamaño descomprimido y tiempos.
Los resultados se registran en la sección "Mediciones Fase 0" de `docs/PROGRESS.md` y en el
reporte de la fase. Este archivo se actualiza con la estructura interna observada.

## 6. Comandos de reproducción

```bash
# Metadatos y recursos
curl -sS "https://datos.produccion.gob.ar/api/3/action/package_show?id=sepa-precios" \
  | jq '.result | {license_title, resources: [.resources[] | {name, description, size, last_modified, url}]}'

# Un día (ejemplo: martes 2026-11-03)
curl -sS -L -A "canasta-personal/0.1 (+https://github.com/juanmas-hub/canasta-personal)" \
  -o data/tmp/sepa_2026-11-03.zip \
  "https://datos.produccion.gob.ar/dataset/6f47ec76-d1ce-4e34-a7e1-621fe9b1d0b5/resource/9dc06241-cc83-44f4-8e25-c9b1636b8bc8/download/sepa_martes.zip"
```
