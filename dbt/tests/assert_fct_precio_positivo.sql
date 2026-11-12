select *
from {{ ref('fct_precio_diario') }}
where precio_lista <= 0
