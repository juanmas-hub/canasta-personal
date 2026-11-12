select
    fecha,
    provincia,
    ean,
    count(*) as n
from {{ ref('agg_precio_ean_diario') }}
group by 1, 2, 3
having count(*) > 1
