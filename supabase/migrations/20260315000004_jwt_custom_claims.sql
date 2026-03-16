-- Migration: JWT Custom Claims Hook
-- After applying this migration, go to:
-- Supabase Dashboard > Authentication > Hooks > Customize Access Token (JWT)
-- and point it to: public.custom_access_token_hook

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  claims  jsonb;
  uid     uuid;
  roles   text[];
  perms   text[];
BEGIN
  uid    := (event->>'user_id')::uuid;
  claims := event->'claims';

  -- Embed roles array into JWT
  SELECT array_agg(role::text ORDER BY role) INTO roles
  FROM public.user_roles
  WHERE user_id = uid;

  claims := jsonb_set(
    claims,
    '{user_roles}',
    to_jsonb(COALESCE(roles, ARRAY[]::text[]))
  );

  -- Embed is_admin convenience boolean (backwards compat)
  claims := jsonb_set(
    claims,
    '{is_admin}',
    to_jsonb(
      'admin'       = ANY(COALESCE(roles, ARRAY[]::text[]))
      OR 'super_admin' = ANY(COALESCE(roles, ARRAY[]::text[]))
    )
  );

  -- Embed email_verified from profiles
  claims := jsonb_set(
    claims,
    '{email_verified}',
    to_jsonb(
      COALESCE(
        (SELECT email_verified FROM public.profiles WHERE id = uid),
        false
      )
    )
  );

  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;

GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM PUBLIC;
