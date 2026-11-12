select
    fecha,
    ean,
    provincia,
    precio_min,
    precio_p25,
    precio_mediana,
    precio_p75,
    precio_max,
    n_sucursales,
    n_observaciones
from {{ ref('stg_sepa__agregados') }}
