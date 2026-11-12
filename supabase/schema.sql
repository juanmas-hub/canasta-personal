-- Esquema para las canastas de los usuarios del dashboard.
-- Correr en el SQL Editor del proyecto Supabase.
-- Requiere que exista auth.users (default de Supabase Auth).

create table if not exists public.baskets (
    user_id uuid primary key default auth.uid(),
    items jsonb not null,                    -- [{ean, label, qty_per_month}]
    provincias text[] not null default '{}',
    updated_at timestamptz not null default now()
);

alter table public.baskets enable row level security;

-- Cada usuario solo ve y edita su propia canasta (RLS por auth.uid()).
create policy "baskets_select_own" on public.baskets
    for select using (auth.uid() = user_id);
create policy "baskets_insert_own" on public.baskets
    for insert with check (auth.uid() = user_id);
create policy "baskets_update_own" on public.baskets
    for update using (auth.uid() = user_id);

-- Para el flujo v1 (alta inmediata sin email de confirmación), deshabilitar en
-- Authentication → Sign In / Up → Email: "Confirm email".
