with precios as (
    select
        fecha,
        cadena,
        ean,
        median(precio_lista) as precio
    from {{ ref('fct_precio_diario') }}
    group by 1, 2, 3
),

basket as (
    select ean, qty_per_month
    from {{ source('basket', 'basket_items') }}
),

fechas_cadenas as (
    select distinct fecha, cadena from precios
),

joined as (
    select
        f.fecha,
        f.cadena,
        b.ean,
        b.qty_per_month,
        p.precio
    from fechas_cadenas f
    cross join basket b
    left join precios p
        on p.fecha = f.fecha
        and p.cadena = f.cadena
        and p.ean = b.ean
)

select
    fecha,
    cadena,
    sum(qty_per_month * coalesce(precio, 0)) as costo,
    sum(case when precio is not null then qty_per_month else 0 end)
        / nullif(sum(qty_per_month), 0) as cobertura,
    count(*) as n_items,
    count(precio) as n_items_con_precio
from joined
group by 1, 2
