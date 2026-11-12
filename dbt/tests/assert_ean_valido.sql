select *
from {{ ref('fct_precio_diario') }}
where ean !~ '^[0-9]+$'
   or length(ean) not in (8, 12, 13, 14)
