select
    fecha,
    id_comercio,
    id_bandera,
    id_sucursal,
    ean,
    count(*) as n
from {{ ref('fct_precio_diario') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
