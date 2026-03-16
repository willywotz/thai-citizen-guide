-- Migration: Expand role enum + extend profiles + update handle_new_user trigger

-- 1. Expand app_role enum with new roles
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'super_admin';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'moderator';
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'api_user';

-- 2. Extend profiles table with auth/provider tracking columns
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS email_verified     boolean     NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS email_verified_at  timestamptz,
  ADD COLUMN IF NOT EXISTS auth_provider      text        NOT NULL DEFAULT 'email',
  ADD COLUMN IF NOT EXISTS oauth_provider_id  text,
  ADD COLUMN IF NOT EXISTS last_sign_in_at    timestamptz,
  ADD COLUMN IF NOT EXISTS is_active          boolean     NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS metadata           jsonb       NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_profiles_auth_provider
  ON public.profiles(auth_provider);

-- 3. Update handle_new_user trigger to populate new columns + auto-assign 'user' role
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_provider  text;
  v_verified  boolean;
BEGIN
  v_provider := COALESCE(NEW.raw_app_meta_data->>'provider', 'email');
  -- OAuth providers auto-verify email
  v_verified := CASE
    WHEN v_provider IN ('google', 'github') THEN true
    ELSE COALESCE(NEW.email_confirmed_at IS NOT NULL, false)
  END;

  INSERT INTO public.profiles (
    id,
    display_name,
    avatar_url,
    auth_provider,
    oauth_provider_id,
    email_verified,
    email_verified_at
  )
  VALUES (
    NEW.id,
    COALESCE(
      NEW.raw_user_meta_data->>'full_name',
      NEW.raw_user_meta_data->>'display_name',
      NEW.raw_user_meta_data->>'name',
      split_part(NEW.email, '@', 1)
    ),
    NEW.raw_user_meta_data->>'avatar_url',
    v_provider,
    NEW.raw_app_meta_data->>'sub',
    v_verified,
    CASE WHEN v_verified THEN now() ELSE NULL END
  )
  ON CONFLICT (id) DO UPDATE SET
    email_verified    = EXCLUDED.email_verified,
    email_verified_at = COALESCE(profiles.email_verified_at, EXCLUDED.email_verified_at),
    auth_provider     = EXCLUDED.auth_provider,
    oauth_provider_id = COALESCE(profiles.oauth_provider_id, EXCLUDED.oauth_provider_id),
    updated_at        = now();

  -- Auto-assign 'user' role on first signup
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, 'user')
  ON CONFLICT (user_id, role) DO NOTHING;

  RETURN NEW;
END;
$$;

-- 4. Function to mark email as verified (called from auth hook)
CREATE OR REPLACE FUNCTION public.mark_email_verified(_user_id uuid)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.profiles
  SET email_verified = true,
      email_verified_at = COALESCE(email_verified_at, now()),
      updated_at = now()
  WHERE id = _user_id
    AND email_verified = false;
$$;

-- 5. Expand admin policy on user_roles to cover new roles
-- (existing policy "Admins can manage roles" uses has_role(..., 'admin') which still works)
-- Add super_admin can also manage roles
CREATE POLICY "Super admins can manage all roles" ON public.user_roles
  FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'super_admin'));
