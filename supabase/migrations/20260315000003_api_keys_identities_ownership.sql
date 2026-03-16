-- Migration: API keys table, user identities, and conversation ownership

-- 1. Add user_id ownership to conversations
ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS user_id   uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS is_public boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_conversations_user_id
  ON public.conversations(user_id);

-- Backfill: existing conversations become public (no owner)
UPDATE public.conversations SET is_public = true WHERE user_id IS NULL;

-- 2. API keys table
CREATE TABLE public.api_keys (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name           text        NOT NULL,
  key_prefix     text        NOT NULL,
  key_hash       text        NOT NULL UNIQUE,
  scopes         text[]      NOT NULL DEFAULT '{}',
  expires_at     timestamptz,
  last_used_at   timestamptz,
  last_used_ip   text,
  revoked_at     timestamptz,
  revoked_reason text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_keys_user_id_active
  ON public.api_keys(user_id)
  WHERE revoked_at IS NULL;

CREATE INDEX idx_api_keys_key_hash
  ON public.api_keys(key_hash)
  WHERE revoked_at IS NULL;

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own api keys" ON public.api_keys
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users insert own api keys" ON public.api_keys
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own api keys" ON public.api_keys
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Admins read all api keys" ON public.api_keys
  FOR SELECT TO authenticated
  USING (public.has_permission(auth.uid(), 'api_keys.read.all'));

CREATE POLICY "Admins revoke any api key" ON public.api_keys
  FOR UPDATE TO authenticated
  USING (public.has_permission(auth.uid(), 'api_keys.revoke.all'));

-- 3. User identities table (public mirror of auth.identities for UI use)
CREATE TABLE public.user_identities (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  provider       text        NOT NULL,
  provider_id    text        NOT NULL,
  provider_email text,
  linked_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_id)
);

CREATE INDEX idx_user_identities_user_id
  ON public.user_identities(user_id);

ALTER TABLE public.user_identities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own identities" ON public.user_identities
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Admins read all identities" ON public.user_identities
  FOR SELECT TO authenticated
  USING (public.has_permission(auth.uid(), 'users.read'));

-- Service role inserts via trigger (identity sync)
-- Insert is handled by service role from edge function / auth hook

-- 4. Realtime for api_keys and user_identities
ALTER PUBLICATION supabase_realtime ADD TABLE public.api_keys;
