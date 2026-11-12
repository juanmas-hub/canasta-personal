select
    cast(id_comercio as varchar) as id_comercio,
    cast(id_bandera as varchar) as id_bandera,
    trim(comercio_razon_social) as comercio_razon_social,
    trim(comercio_bandera_nombre) as comercio_bandera_nombre
from {{ source('raw', 'comercios') }}
