select
    cast(fecha as date) as fecha,
    cast(ean as varchar) as ean,
    upper(trim(provincia)) as provincia,
    cast("min" as double) as precio_min,
    cast("p25" as double) as precio_p25,
    cast("mediana" as double) as precio_mediana,
    cast("p75" as double) as precio_p75,
    cast("max" as double) as precio_max,
    cast(n_sucursales as integer) as n_sucursales,
    cast(n_observaciones as integer) as n_observaciones
from {{ source('raw', 'agg_precio_ean_diario') }}
