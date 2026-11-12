# Modelo de datos

## Granularidad

| Modelo | Grano | Clave |
|---|---|---|
| `stg_sepa__precios` | fecha × sucursal × EAN | — |
| `stg_sepa__agregados` | fecha × provincia × EAN | — |
| `int_precio_normalizado` | fecha × sucursal × EAN | — |
| `dim_producto` | EAN | `ean` |
| `dim_sucursal` | comercio × bandera × sucursal | `id_comercio`, `id_bandera`, `id_sucursal` |
| `dim_fecha` | fecha | `fecha` |
| `fct_precio_diario` | fecha × sucursal × EAN (tracked) | `fecha`, `id_comercio`, `id_bandera`, `id_sucursal`, `ean` |
| `agg_precio_ean_diario` | fecha × provincia × EAN | `fecha`, `provincia`, `ean` |
| `mart_canasta_costo_diario` | fecha × cadena | `fecha`, `cadena` |
| `mart_indice_canasta` | fecha | `fecha` |
| `mart_ranking_cadenas` | fecha × cadena | `fecha`, `cadena` |
| `mart_catalogo` | EAN tracked | `ean` |
| `mart_precio_ean_diario` | fecha × provincia × EAN tracked | `fecha`, `provincia`, `ean` |
| `mart_precio_ean_cadena` | última fecha × provincia × cadena × EAN tracked | `fecha`, `provincia`, `cadena`, `ean` |

## Reglas

- Clave de producto: EAN-8/12/13/14 con dígito verificador GS1. Los códigos internos
  (`productos_ean = 0`) y los EAN inválidos se excluyen y se cuentan en `rejects`.
- Precio base: `productos_precio_lista`. Las promociones (`promo1`, `promo2`) son métricas
  separadas y no entran en el índice.
- Precio diario por EAN: mediana entre sucursales del alcance (y por cadena para el ranking).
- Outlier: precio > 10× o < 0,1× la mediana del EAN ese día. Se marca, no se borra.

## Índice

`Índice_t = 100 × Σ(qᵢ · pᵢ,t) / Σ(qᵢ · pᵢ,base)`

- `qᵢ`: `qty_per_month` de `basket.yml`.
- Fecha base: primera fecha con cobertura ≥ 90% del peso de la canasta.
- Cobertura: peso de ítems con precio / peso total.
- Carry-forward: último precio por hasta 3 días; después el día queda `completo = false`.

## Ranking y ahorro

- `costo_mejor_cadena`: cadena completa más barata (cobertura ≥ 90%).
- `costo_surtido`: sumar cada ítem al precio mínimo entre todas las cadenas.
- `ahorro_potencial = costo_mejor_cadena - costo_surtido`.
- `ranking` solo se asigna a cadenas completas; las incompletas quedan al final sin posición.

## Archivos publicados en la rama `data`

| Archivo | Contenido |
|---|---|
| `marts/mart_indice_canasta.parquet` | Serie del índice, costo, cobertura y base (canasta del repo). |
| `marts/mart_ranking_cadenas.parquet` | Ranking y resumen de ahorro (canasta del repo). |
| `marts/mart_canasta_detalle.parquet` | Detalle por cadena × producto de la última fecha (canasta del repo). |
| `marts/mart_salud.parquet` | Última fecha, filas, rechazos y cobertura. |
| `marts/mart_catalogo.parquet` | EANs tracked: descripción, marca, presentación y cantidad de cadenas. |
| `marts/mart_precio_ean_diario.parquet` | Mediana por fecha × provincia × EAN (índice de cualquier canasta). |
| `marts/mart_precio_ean_cadena.parquet` | Mediana por provincia × cadena × EAN de la última fecha (ranking). |

## Canasta del usuario

La UI arma la canasta sobre `mart_catalogo` y calcula en sesión el índice y el ranking con
los módulos de `canasta.index`/`canasta.ranking` (ADR-018). Con cuenta configurada, la canasta
persiste en la tabla `baskets` de Supabase (`user_id`, `items` jsonb, `provincias`), protegida
por RLS `auth.uid() = user_id`.
