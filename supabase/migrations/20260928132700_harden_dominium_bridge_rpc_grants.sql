-- Harden the Supabase RPC surface used by the Hostinger bridge.
--
-- Bridge RPCs that accept p_bridge_token intentionally remain executable by anon:
-- the Node bridge authenticates to PostgREST with the publishable key and proves
-- server possession of the separate DOMINIUM bridge token inside each function.
-- Authenticated browser users do not need direct access to those bridge-only RPCs.

revoke execute on function public.dominium_web_pending_count() from anon;

-- This helper is only called by SECURITY DEFINER bridge functions. Keeping it
-- private removes a token-validity oracle from the exposed RPC surface.
revoke execute on function public.dominium_web_bridge_ok(text)
  from anon, authenticated;

revoke execute on function public.dominium_web_audit(
  bigint,text,text,text,text,text,text,text
) from authenticated;

revoke execute on function public.dominium_web_list_users(text)
  from authenticated;
revoke execute on function public.dominium_web_login_failure(bigint,text)
  from authenticated;
revoke execute on function public.dominium_web_login_success(bigint,text)
  from authenticated;
revoke execute on function public.dominium_web_pending_count(text)
  from authenticated;
revoke execute on function public.dominium_web_profile_lookup(text,text)
  from authenticated;
revoke execute on function public.dominium_web_session_create(
  text,bigint,text,text,text,timestamptz,timestamptz,text
) from authenticated;
revoke execute on function public.dominium_web_session_get(
  text,text,boolean,text
) from authenticated;
revoke execute on function public.dominium_web_session_revoke(text,text)
  from authenticated;
