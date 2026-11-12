select
    s.id_comercio,
    s.id_bandera,
    s.id_sucursal,
    s.sucursales_nombre,
    s.sucursales_tipo,
    s.sucursales_calle,
    s.sucursales_numero,
    s.sucursales_latitud,
    s.sucursales_longitud,
    s.sucursales_barrio,
    s.sucursales_codigo_postal,
    s.sucursales_localidad,
    s.sucursales_provincia,
    c.comercio_razon_social,
    c.comercio_bandera_nombre as cadena
from {{ ref('stg_sepa__sucursales') }} s
left join {{ ref('stg_sepa__comercios') }} c using (id_comercio, id_bandera)
