-- Hosted DOMINIUM auth bridge.
-- Keeps privileged profile data behind authenticated SECURITY DEFINER RPCs.

create or replace function public.dominium_web_current_profile()
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog
as $$
declare
  v_uid uuid := auth.uid();
  v_profile record;
  v_identities jsonb := '{}'::jsonb;
begin
  if v_uid is null then
    return null;
  end if;

  select *
    into v_profile
    from public.dominium_profiles
   where auth_user_id = v_uid
   limit 1;

  if not found then
    return null;
  end if;

  select coalesce(
           jsonb_object_agg(
             i.profile_key,
             jsonb_build_object(
               'linked', true,
               'username', i.imperium_username,
               'controller_id', i.controller_id,
               'verified_at', i.verified_at
             )
           ),
           '{}'::jsonb
         )
    into v_identities
    from public.dominium_imperium_identities i
   where i.user_id = v_profile.id;

  return jsonb_build_object(
    'id', v_profile.id,
    'username', v_profile.username,
    'display_name', v_profile.display_name,
    'role', v_profile.role,
    'status', v_profile.status,
    'contact_email', coalesce(v_profile.contact_email, ''),
    'created_at', v_profile.created_at,
    'approved_at', v_profile.approved_at,
    'rejected_at', v_profile.rejected_at,
    'rejection_reason', coalesce(v_profile.rejection_reason, ''),
    'last_login_at', v_profile.last_login_at,
    'imperium_identities', v_identities,
    'imperium_identity', jsonb_build_object(
      'linked', jsonb_object_length(v_identities) > 0,
      'profiles', coalesce(
        (select jsonb_agg(key order by key) from jsonb_object_keys(v_identities) as t(key)),
        '[]'::jsonb
      )
    )
  );
end;
$$;

revoke all on function public.dominium_web_current_profile() from public, anon;
grant execute on function public.dominium_web_current_profile() to authenticated;

create or replace function public.dominium_web_admin_users()
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog
as $$
declare
  v_uid uuid := auth.uid();
  v_role text;
  v_status text;
  v_result jsonb;
begin
  select role, status
    into v_role, v_status
    from public.dominium_profiles
   where auth_user_id = v_uid
   limit 1;

  if v_role is distinct from 'admin' or v_status is distinct from 'active' then
    raise exception 'forbidden';
  end if;

  select coalesce(jsonb_agg(item order by (item->>'id')::bigint), '[]'::jsonb)
    into v_result
    from (
      select jsonb_build_object(
        'id', p.id,
        'username', p.username,
        'display_name', p.display_name,
        'role', p.role,
        'status', p.status,
        'contact_email', coalesce(p.contact_email, ''),
        'created_at', p.created_at,
        'approved_at', p.approved_at,
        'rejected_at', p.rejected_at,
        'rejection_reason', coalesce(p.rejection_reason, ''),
        'last_login_at', p.last_login_at,
        'imperium_identities',
          coalesce((
            select jsonb_object_agg(
              i.profile_key,
              jsonb_build_object(
                'linked', true,
                'username', i.imperium_username,
                'controller_id', i.controller_id,
                'verified_at', i.verified_at
              )
            )
            from public.dominium_imperium_identities i
            where i.user_id = p.id
          ), '{}'::jsonb)
      ) as item
      from public.dominium_profiles p
    ) s;

  return v_result;
end;
$$;

revoke all on function public.dominium_web_admin_users() from public, anon;
grant execute on function public.dominium_web_admin_users() to authenticated;
