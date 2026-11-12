with dates as (
    select fecha from {{ ref('stg_sepa__precios') }}
    union
    select fecha from {{ ref('stg_sepa__agregados') }}
)

select distinct
    fecha,
    extract(year from fecha) as anio,
    extract(month from fecha) as mes,
    extract(day from fecha) as dia,
    dayname(fecha) as dia_semana
from dates
