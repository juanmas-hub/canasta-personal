# Bloqueos que requieren acción humana

Actualizado: 2026-11-10.

## B-001 — Deploy público en Streamlit Community Cloud

**Qué falta:** crear la app en https://share.streamlit.io con la cuenta de GitHub
`juanmas-hub`. El alta requiere login OAuth humano; el agente no puede completarla.

**Pasos exactos (cuando el repo esté pusheado y la rama `data` publicada):**

1. Entrar a https://share.streamlit.io con la cuenta `juanmas-hub`.
2. "New app" → repositorio `juanmas-hub/canasta-personal`, branch `main`,
   main file `dashboard/app.py`.
3. En "Advanced settings" → "Secrets", pegar:
   ```toml
   SUPABASE_URL = "https://<proyecto>.supabase.co"
   SUPABASE_ANON_KEY = "<anon key>"
   ```
   Sin esos secretos la app muestra un error de configuración y no abre (cuentas obligatorias).
4. Copiar la URL pública y agregarla al README y a `docs/PROGRESS.md`.

**Impacto:** sin este paso no hay dashboard público ni usuarios reales. El resto del pipeline
(CI, Actions, marts) sí queda operativo.

## B-002 — Push, primera corrida de CI y rama `data`

**Qué falta:** el repositorio todavía no tiene commits ni está pusheado. El agente no hace
`git commit`/`git push` sin pedido explícito. Sin eso no se puede verificar CI ni ejecutar el
workflow programado en GitHub.

**Pasos exactos:**

1. Revisar y commitear el árbol actual; pushear `main` a `git@github.com:juanmas-hub/canasta-personal.git`.
2. Verificar que `CI` quede verde en la pestaña Actions.
3. Ejecutar una vez `daily-sepa` con `workflow_dispatch` (o `make ingest DATE=... && make publish-data`).
4. Confirmar que exista la rama `data` con `marts/*.parquet` y que `mart_indice_canasta` tenga
   más de una fecha tras dos corridas (valida el cache de `data/raw`).
5. Recién entonces hacer B-001 (Streamlit Cloud).

**Impacto:** los workflows están escritos y el demo Docker/local funciona, pero la "Definición
de terminado" no puede marcar CI verde ni corrida programada real hasta este paso.

## B-003 — Proyecto Supabase (cuentas obligatorias)

**Qué falta:** crear el proyecto en https://supabase.com (requiere cuenta humana) y cargar los
secretos. Sin esto el dashboard no abre.

**Pasos exactos:**

1. Crear un proyecto free en https://supabase.com.
2. SQL Editor → pegar y ejecutar `supabase/schema.sql` (tabla `baskets` + RLS).
3. Authentication → Providers → Email: deshabilitar "Confirm email" (v1 sin confirmación).
4. Copiar `Project URL` y `anon public key` (Settings → API).
5. Pegarlos como secrets en Streamlit Cloud (B-001, paso 3) y, opcionalmente, como secrets del
   repo (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) para el workflow `supabase-ping`.
6. Probar con dos cuentas: cada una ve solo su canasta (aislamiento RLS).

**Impacto:** sin este paso la app muestra "Faltan SUPABASE_URL y SUPABASE_ANON_KEY".
