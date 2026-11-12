select *
from {{ ref('agg_precio_ean_diario') }}
where precio_mediana <= 0
