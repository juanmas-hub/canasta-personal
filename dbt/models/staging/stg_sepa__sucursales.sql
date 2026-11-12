select
    cast(id_comercio as varchar) as id_comercio,
    cast(id_bandera as varchar) as id_bandera,
    cast(id_sucursal as varchar) as id_sucursal,
    trim(sucursales_nombre) as sucursales_nombre,
    trim(sucursales_tipo) as sucursales_tipo,
    trim(sucursales_calle) as sucursales_calle,
    trim(sucursales_numero) as sucursales_numero,
    cast(sucursales_latitud as double) as sucursales_latitud,
    cast(sucursales_longitud as double) as sucursales_longitud,
    trim(sucursales_barrio) as sucursales_barrio,
    trim(sucursales_codigo_postal) as sucursales_codigo_postal,
    trim(sucursales_localidad) as sucursales_localidad,
    upper(trim(sucursales_provincia)) as sucursales_provincia
from {{ source('raw', 'sucursales') }}
