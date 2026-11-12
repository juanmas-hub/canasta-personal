select f.*
from {{ ref('fct_precio_diario') }} f
left join {{ ref('dim_sucursal') }} s
    on f.id_comercio = s.id_comercio
    and f.id_bandera = s.id_bandera
    and f.id_sucursal = s.id_sucursal
where s.id_sucursal is null
