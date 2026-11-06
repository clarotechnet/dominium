-- Dominium / Imperium, phase 2: individual serial history treatment.
-- Apply ONLY to operational project haqzzxpocwzntyudrbch.
-- Requires preceding migration 20261105173000_dominium_imperium_live_periods.sql.
begin;

create table if not exists public.dominium_imperium_tratamento_itens (
  consulta_id uuid not null
    references public.dominium_imperium_consultas(id) on delete cascade,
  serial text not null
    check (char_length(serial) between 4 and 100 and serial=upper(btrim(serial))),
  situacao text not null
    check (situacao in ('historico_verificado','sem_movimentos','erro_consulta','formato_nao_suportado')),
  evidencia jsonb not null default '{}'::jsonb
    check (jsonb_typeof(evidencia)='object'),
  tentativas smallint not null default 1 check (tentativas between 1 and 3),
  tratado_em timestamptz not null default now(),
  tratado_por text not null check (char_length(tratado_por) between 1 and 100),
  primary key (consulta_id,serial)
);

create index if not exists idx_dominium_imperium_tratamento_consulta_situacao
  on public.dominium_imperium_tratamento_itens (consulta_id,situacao);

alter table public.dominium_imperium_tratamento_itens enable row level security;
revoke all on public.dominium_imperium_tratamento_itens from public,anon,authenticated;
grant select,insert,update,delete on public.dominium_imperium_tratamento_itens to service_role;

comment on table public.dominium_imperium_tratamento_itens is
  'Tratativa individual, somente leitura, dos seriais coletados no relatorio Imperium; evidencia de historico nao prova posse atual.';

commit;
