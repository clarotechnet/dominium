-- These tables are server-owned. Explicit deny policies document the intended
-- browser posture while service_role / SECURITY DEFINER server functions continue
-- to operate with their normal privileges.

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='dominium_sessions'
      and policyname='dominium_sessions_deny_direct'
  ) then
    create policy dominium_sessions_deny_direct
      on public.dominium_sessions
      for all to anon, authenticated
      using (false) with check (false);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='dominium_operator_audit'
      and policyname='dominium_operator_audit_deny_direct'
  ) then
    create policy dominium_operator_audit_deny_direct
      on public.dominium_operator_audit
      for all to anon, authenticated
      using (false) with check (false);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='dominium_operation_tickets'
      and policyname='dominium_operation_tickets_deny_direct'
  ) then
    create policy dominium_operation_tickets_deny_direct
      on public.dominium_operation_tickets
      for all to anon, authenticated
      using (false) with check (false);
  end if;
end $$;
