-- DOMINIUM only: live DataSnap period snapshots persisted in operational Supabase.
-- Target project: haqzzxpocwzntyudrbch (NEVER the financial Supabase project).
-- Back-end service_role only. No public Data API reads or writes.
-- Run with SQL editor on the operational project before enabling Live Sync.
begin;

create table if not exists public.dominium_imperium_consultas (
  id uuid primary key default gen_random_uuid(),
  cidade text not null check (cidade in ('natal','mossoro','recife','fortaleza')),
  data_inicio date not null,
  data_fim date not null,
  solicitado_por text not null check (char_length(solicitado_por) between 1 and 100),
  estado text not null default 'processando'
    check (estado in ('processando','concluido','falhou')),
  criado_em timestamptz not null default now(),
  concluido_em timestamptz,
  fonte text not null default 'datasnap_equipamentos_utilizados'
    check (fonte = 'datasnap_equipamentos_utilizados'),
  total_consolidado integer not null default 0 check (total_consolidado between 0 and 60000),
  total_os integer not null default 0 check (total_os between 0 and 60000),
  total_seriais integer not null default 0 check (total_seriais between 0 and 60000),
  hash_conteudo text check (hash_conteudo is null or hash_conteudo ~ '^[a-f0-9]{64}$'),
  tratamento text not null default 'fonte_tratada'
    check (tratamento = 'fonte_tratada'),
  seis_abas_completas boolean not null default false check (seis_abas_completas = false),
  observacoes jsonb not null default '{}'::jsonb check (jsonb_typeof(observacoes) = 'object'),
  check (data_fim >= data_inicio and data_fim - data_inicio <= 30)
);

create table if not exists public.dominium_imperium_consulta_lotes (
  consulta_id uuid not null references public.dominium_imperium_consultas(id) on delete cascade,
  categoria text not null check (categoria in ('consolidado','por_os','seriais_tratados')),
  indice_lote integer not null check (indice_lote between 0 and 1000),
  registros jsonb not null check (jsonb_typeof(registros) = 'array'),
  quantidade integer not null check (quantidade between 0 and 200),
  primary key (consulta_id,categoria,indice_lote),
  check (quantidade = jsonb_array_length(registros))
);

create index if not exists idx_dominium_imperium_consultas_cidade_data
  on public.dominium_imperium_consultas(cidade,data_inicio,data_fim,criado_em desc)
  where estado='concluido';

create index if not exists idx_dominium_imperium_consultas_hash
  on public.dominium_imperium_consultas(cidade,data_inicio,data_fim,hash_conteudo)
  where estado='concluido';

alter table public.dominium_imperium_consultas enable row level security;
alter table public.dominium_imperium_consulta_lotes enable row level security;

revoke all on public.dominium_imperium_consultas from public, anon, authenticated;
revoke all on public.dominium_imperium_consulta_lotes from public, anon, authenticated;
grant select,insert,update,delete on public.dominium_imperium_consultas to service_role;
grant select,insert,update,delete on public.dominium_imperium_consulta_lotes to service_role;

comment on table public.dominium_imperium_consultas is
'Snapshots de equipamentos usados no Imperium via DataSnap; nao representam a analise final Atlas de seis abas';
comment on table public.dominium_imperium_consulta_lotes is
'Lotes de registros originais e seriais normalizados; somente servidor local com service_role';

commit;
