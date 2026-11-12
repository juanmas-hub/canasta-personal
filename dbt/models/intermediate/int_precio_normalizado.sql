with base as (
    select * from {{ ref('stg_sepa__precios') }}
),

stats as (
    select
        fecha,
        ean,
        provincia,
        median(precio_lista) as mediana
    from base
    group by 1, 2, 3
)

select
    b.*,
    b.precio_lista / nullif(b.cantidad_presentacion, 0) as precio_por_unidad,
    s.mediana,
    coalesce(
        b.precio_lista > 10 * s.mediana or b.precio_lista < 0.1 * s.mediana,
        false
    ) as es_outlier
from base b
left join stats s using (fecha, ean, provincia)
