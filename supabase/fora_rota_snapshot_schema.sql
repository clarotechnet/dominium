-- Fora de Rota: server-only immutable snapshot versions.
create table public.dominium_fora_rota_snapshots (
  profile text not null check (profile in ('natal','fortaleza','mossoro','recife','unassigned')),
  kind text not null check (kind in ('claro','clean106','legacy_sent')),
  revision integer not null check (revision > 0),
  records jsonb not null check (jsonb_typeof(records) = 'array' and jsonb_array_length(records) <= 50000 and octet_length(records::text) <= 5242880),
  source_name text not null check (char_length(source_name) between 1 and 200),
  actor_id bigint not null check (actor_id > 0),
  created_at timestamptz not null default now(),
  primary key (profile,kind,revision),
  check (profile <> 'unassigned' or kind = 'legacy_sent')
);
alter table public.dominium_fora_rota_snapshots enable row level security;
revoke all on public.dominium_fora_rota_snapshots from public, anon, authenticated, service_role;
grant select, insert on public.dominium_fora_rota_snapshots to service_role;

create function public.dominium_fora_rota_snapshot_put(
  p_profile text, p_kind text, p_expected_revision integer, p_records jsonb,
  p_source_name text, p_actor_id bigint
) returns jsonb
language plpgsql security invoker set search_path = pg_catalog, public
as $$
declare old_row public.dominium_fora_rota_snapshots%rowtype;
declare current_rev integer;
begin
  if p_profile not in ('natal','fortaleza','mossoro','recife','unassigned')
     or p_kind not in ('claro','clean106','legacy_sent')
     or (p_profile = 'unassigned' and p_kind <> 'legacy_sent')
     or p_expected_revision is null or p_expected_revision < 0
     or p_actor_id is null or p_actor_id <= 0
     or p_records is null or jsonb_typeof(p_records) <> 'array'
     or jsonb_array_length(p_records) > 50000
     or octet_length(p_records::text) > 5242880
     or p_source_name is null or char_length(p_source_name) not between 1 and 200 then
    raise exception 'invalid snapshot';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('dominium-fora-rota:' || p_profile || ':' || p_kind, 0));
  select * into old_row from public.dominium_fora_rota_snapshots
    where profile = p_profile and kind = p_kind order by revision desc limit 1;
  current_rev := coalesce(old_row.revision,0);
  if old_row.records = p_records then
    return jsonb_build_object('ok',true,'revision',current_rev,'unchanged',true);
  end if;
  if current_rev <> p_expected_revision then
    return jsonb_build_object('ok',false,'conflict',true,'revision',current_rev);
  end if;
  insert into public.dominium_fora_rota_snapshots(profile,kind,revision,records,source_name,actor_id)
    values(p_profile,p_kind,current_rev+1,p_records,p_source_name,p_actor_id);
  return jsonb_build_object('ok',true,'revision',current_rev+1,'unchanged',false);
end;
$$;
revoke all on function public.dominium_fora_rota_snapshot_put(text,text,integer,jsonb,text,bigint) from public, anon, authenticated, service_role;
grant execute on function public.dominium_fora_rota_snapshot_put(text,text,integer,jsonb,text,bigint) to service_role;
