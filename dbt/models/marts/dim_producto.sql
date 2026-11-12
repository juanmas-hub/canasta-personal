select
    ean,
    mode(descripcion) as descripcion,
    mode(marca) as marca,
    any_value(cantidad_presentacion) as cantidad_presentacion,
    any_value(unidad_presentacion) as unidad_presentacion
from {{ ref('int_precio_normalizado') }}
group by ean
