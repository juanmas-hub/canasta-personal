# Limitaciones

- **Histórico corto:** el sitio publica solo los últimos 7 ZIPs diarios. No hay backfill
  histórico; el índice empieza a tener serie desde la primera corrida.
- **Precios informados, no de góndola:** cada cadena informa sus precios al SEPA. No son una
  foto en vivo ni incluyen errores de carga de la cadena.
- **Alcance v1:** `AR-C` (CABA) y `AR-B` (Buenos Aires). No existe un código GBA/AMBA; el
  alcance se configura con códigos ISO 3166-2.
- **EAN internos:** productos pesables o sin GTIN usan `productos_ean = 0`; se excluyen y se
  reportan en `rejects`. No hay fuzzy matching de descripciones en v1.
- **Origen malformado:** `sucursales.csv` puede traer `\r\n` dentro de filas lógicas, líneas
  cortas, NULs y footers. La ingesta los normaliza; si cambia el esquema, falla explícito.
- **Canasta fija por corrida → canasta en la UI:** el dashboard ahora permite armar la canasta
  desde el navegador (búsqueda en el catálogo, cantidades, provincia) y calcular índice y
  ranking en sesión (ADR-016/018). Con cuenta (Supabase, opcional) la canasta persiste entre
  visitas; sin cuenta vive en la sesión y se respalda exportando `basket.yml`.
- **Catálogo limitado a los EANs tracked:** la UI ofrece ~2.500 productos (canasta del repo +
  top-N por cobertura). Un `basket.yml` con EANs fuera de ese set se carga igual, pero esos
  ítems quedan sin precio y bajan la cobertura.
- **Mediana de medianas por provincia:** con varias provincias seleccionadas, el precio por
  EAN/cadena es la mediana de las medianas provinciales; con una sola provincia es exacta.
- **Cuentas obligatorias vía Supabase:** el dashboard exige registro (email + contraseña) y
  depende de `SUPABASE_URL`/`SUPABASE_ANON_KEY` configurados. Sin eso muestra un error de
  configuración y no abre. Confirmación de email deshabilitada en v1; la RLS debe probarse
  con dos usuarios antes de un deploy público. El free tier de Supabase pausa el proyecto
  tras ~1 semana sin actividad (mitigado por el workflow semanal `supabase-ping`).
- **dbt no incremental:** cada partición reconstruye todos los marts. Con una sola fecha es
  barato; un backfill grande repetiría trabajo.
- **Índice propio:** no es inflación oficial, IPC ni una canasta representativa del consumo
  de los hogares. Es el costo de los productos y cantidades que definió el usuario.
- **Licencia ambigua:** CKAN declara CC BY 4.0 y `preciosclaros.gob.ar` CC BY 2.5 AR. Se cita
  CC BY 4.0 y se deja la discrepancia documentada.
- **Deploy público:** Streamlit Community Cloud requiere autorización OAuth humana; ver
  `BLOCKERS.md`.
