-- Migration: Full RLS Policy Overhaul
-- Replaces all public-access policies with proper auth-based policies

-- =========================================================
-- CONVERSATIONS
-- =========================================================
DROP POLICY IF EXISTS "Public read conversations"   ON public.conversations;
DROP POLICY IF EXISTS "Public insert conversations" ON public.conversations;
DROP POLICY IF EXISTS "Public update conversations" ON public.conversations;
DROP POLICY IF EXISTS "Public delete conversations" ON public.conversations;

-- Users read their own conversations or public ones
CREATE POLICY "Users read own or public conversations" ON public.conversations
  FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR is_public = true);

-- Staff (admin/moderator) can read all
CREATE POLICY "Staff read all conversations" ON public.conversations
  FOR SELECT TO authenticated
  USING (public.has_permission(auth.uid(), 'conversations.read.all'));

-- Authenticated users can insert (ownership set at insert time)
CREATE POLICY "Users insert conversations" ON public.conversations
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

-- Users update their own conversations
CREATE POLICY "Users update own conversations" ON public.conversations
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid());

-- Staff can update any conversation
CREATE POLICY "Staff update any conversation" ON public.conversations
  FOR UPDATE TO authenticated
  USING (public.has_permission(auth.uid(), 'conversations.write.all'));

-- Users delete their own conversations
CREATE POLICY "Users delete own conversations" ON public.conversations
  FOR DELETE TO authenticated
  USING (user_id = auth.uid());

-- Staff can delete any conversation
CREATE POLICY "Staff delete any conversation" ON public.conversations
  FOR DELETE TO authenticated
  USING (public.has_permission(auth.uid(), 'conversations.delete.all'));

-- Anon users can read public conversations (for public portal)
CREATE POLICY "Anon read public conversations" ON public.conversations
  FOR SELECT TO anon
  USING (is_public = true);

-- =========================================================
-- MESSAGES
-- =========================================================
DROP POLICY IF EXISTS "Public read messages"   ON public.messages;
DROP POLICY IF EXISTS "Public insert messages" ON public.messages;
DROP POLICY IF EXISTS "Public update messages" ON public.messages;
DROP POLICY IF EXISTS "Public delete messages" ON public.messages;

-- Messages inherit access from their parent conversation
CREATE POLICY "Users read messages of accessible conversations" ON public.messages
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.conversations c
      WHERE c.id = conversation_id
        AND (c.user_id = auth.uid() OR c.is_public = true)
    )
  );

CREATE POLICY "Staff read all messages" ON public.messages
  FOR SELECT TO authenticated
  USING (public.has_permission(auth.uid(), 'conversations.read.all'));

CREATE POLICY "Users insert messages into own conversations" ON public.messages
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.conversations c
      WHERE c.id = conversation_id AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users update messages in own conversations" ON public.messages
  FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.conversations c
      WHERE c.id = conversation_id AND c.user_id = auth.uid()
    )
  );

CREATE POLICY "Users delete messages in own conversations" ON public.messages
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.conversations c
      WHERE c.id = conversation_id AND c.user_id = auth.uid()
    )
  );

-- Anon read messages of public conversations (public portal)
CREATE POLICY "Anon read public conversation messages" ON public.messages
  FOR SELECT TO anon
  USING (
    EXISTS (
      SELECT 1 FROM public.conversations c
      WHERE c.id = conversation_id AND c.is_public = true
    )
  );

-- =========================================================
-- AGENCIES
-- =========================================================
DROP POLICY IF EXISTS "Public read agencies"   ON public.agencies;
DROP POLICY IF EXISTS "Public insert agencies" ON public.agencies;
DROP POLICY IF EXISTS "Public update agencies" ON public.agencies;
DROP POLICY IF EXISTS "Public delete agencies" ON public.agencies;

-- Public read (both anon and authenticated — needed for public portal)
CREATE POLICY "Anyone reads agencies" ON public.agencies
  FOR SELECT USING (true);

-- Admin/super_admin can write agencies
CREATE POLICY "Admin writes agencies" ON public.agencies
  FOR INSERT TO authenticated
  WITH CHECK (public.has_permission(auth.uid(), 'agencies.write'));

CREATE POLICY "Admin updates agencies" ON public.agencies
  FOR UPDATE TO authenticated
  USING (public.has_permission(auth.uid(), 'agencies.write'));

CREATE POLICY "Admin deletes agencies" ON public.agencies
  FOR DELETE TO authenticated
  USING (public.has_permission(auth.uid(), 'agencies.delete'));

-- =========================================================
-- CONNECTION_LOGS
-- =========================================================
DROP POLICY IF EXISTS "Public read connection_logs"   ON public.connection_logs;
DROP POLICY IF EXISTS "Public insert connection_logs" ON public.connection_logs;

-- Only users with dashboard.read permission can read logs
CREATE POLICY "Dashboard readers read connection logs" ON public.connection_logs
  FOR SELECT TO authenticated
  USING (public.has_permission(auth.uid(), 'dashboard.read'));

-- Insert is done by edge functions using service role key (bypasses RLS)

-- =========================================================
-- PROFILES: Extend admin policy to use has_permission
-- =========================================================
DROP POLICY IF EXISTS "Admins can read all profiles" ON public.profiles;

CREATE POLICY "Staff read all profiles" ON public.profiles
  FOR SELECT TO authenticated
  USING (public.has_permission(auth.uid(), 'users.read'));

-- Add update-by-admin policy
CREATE POLICY "Staff update profiles" ON public.profiles
  FOR UPDATE TO authenticated
  USING (
    auth.uid() = id
    OR public.has_permission(auth.uid(), 'users.write')
  );

-- =========================================================
-- USER_ROLES: Tighten policies
-- =========================================================
DROP POLICY IF EXISTS "Admins can manage roles" ON public.user_roles;

-- Admin can assign non-privileged roles only
CREATE POLICY "Admin manages limited roles" ON public.user_roles
  FOR ALL TO authenticated
  USING (
    public.has_role(auth.uid(), 'admin')
    AND role NOT IN ('admin', 'super_admin')
  );
