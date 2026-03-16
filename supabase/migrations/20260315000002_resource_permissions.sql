-- Migration: Resource permissions RBAC system

-- 1. Create app_permission enum
CREATE TYPE public.app_permission AS ENUM (
  'conversations.read.own',
  'conversations.read.all',
  'conversations.write.own',
  'conversations.write.all',
  'conversations.delete.own',
  'conversations.delete.all',
  'agencies.read',
  'agencies.write',
  'agencies.delete',
  'users.read',
  'users.write',
  'users.delete',
  'users.roles.assign',
  'api_keys.read.own',
  'api_keys.read.all',
  'api_keys.write.own',
  'api_keys.write.all',
  'api_keys.revoke.own',
  'api_keys.revoke.all',
  'dashboard.read',
  'system.config'
);

-- 2. Role-to-permission mapping table
CREATE TABLE public.role_permissions (
  id         uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
  role       app_role       NOT NULL,
  permission app_permission NOT NULL,
  UNIQUE (role, permission)
);

ALTER TABLE public.role_permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read role permissions" ON public.role_permissions
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Super admins manage role permissions" ON public.role_permissions
  FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'super_admin'));

-- 3. Seed default permissions per role

-- super_admin: everything
INSERT INTO public.role_permissions (role, permission) VALUES
  ('super_admin', 'conversations.read.own'),
  ('super_admin', 'conversations.read.all'),
  ('super_admin', 'conversations.write.own'),
  ('super_admin', 'conversations.write.all'),
  ('super_admin', 'conversations.delete.own'),
  ('super_admin', 'conversations.delete.all'),
  ('super_admin', 'agencies.read'),
  ('super_admin', 'agencies.write'),
  ('super_admin', 'agencies.delete'),
  ('super_admin', 'users.read'),
  ('super_admin', 'users.write'),
  ('super_admin', 'users.delete'),
  ('super_admin', 'users.roles.assign'),
  ('super_admin', 'api_keys.read.own'),
  ('super_admin', 'api_keys.read.all'),
  ('super_admin', 'api_keys.write.own'),
  ('super_admin', 'api_keys.write.all'),
  ('super_admin', 'api_keys.revoke.own'),
  ('super_admin', 'api_keys.revoke.all'),
  ('super_admin', 'dashboard.read'),
  ('super_admin', 'system.config'),

-- admin: most things except user deletion and system.config
  ('admin', 'conversations.read.own'),
  ('admin', 'conversations.read.all'),
  ('admin', 'conversations.write.own'),
  ('admin', 'conversations.write.all'),
  ('admin', 'conversations.delete.own'),
  ('admin', 'conversations.delete.all'),
  ('admin', 'agencies.read'),
  ('admin', 'agencies.write'),
  ('admin', 'users.read'),
  ('admin', 'users.write'),
  ('admin', 'api_keys.read.own'),
  ('admin', 'api_keys.read.all'),
  ('admin', 'api_keys.write.own'),
  ('admin', 'api_keys.revoke.own'),
  ('admin', 'api_keys.revoke.all'),
  ('admin', 'dashboard.read'),

-- moderator: read-all conversations, manage own, read agencies/users
  ('moderator', 'conversations.read.own'),
  ('moderator', 'conversations.read.all'),
  ('moderator', 'conversations.write.own'),
  ('moderator', 'conversations.delete.own'),
  ('moderator', 'agencies.read'),
  ('moderator', 'users.read'),
  ('moderator', 'api_keys.read.own'),
  ('moderator', 'api_keys.write.own'),
  ('moderator', 'api_keys.revoke.own'),
  ('moderator', 'dashboard.read'),

-- user: own resources only
  ('user', 'conversations.read.own'),
  ('user', 'conversations.write.own'),
  ('user', 'conversations.delete.own'),
  ('user', 'agencies.read'),
  ('user', 'api_keys.read.own'),
  ('user', 'api_keys.write.own'),
  ('user', 'api_keys.revoke.own'),

-- api_user: programmatic access only
  ('api_user', 'conversations.read.own'),
  ('api_user', 'conversations.write.own'),
  ('api_user', 'agencies.read'),
  ('api_user', 'api_keys.read.own');

-- 4. has_permission function: checks if user has a permission via any of their roles
CREATE OR REPLACE FUNCTION public.has_permission(_user_id uuid, _permission app_permission)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles ur
    JOIN public.role_permissions rp ON rp.role = ur.role
    WHERE ur.user_id = _user_id
      AND rp.permission = _permission
  )
$$;

-- 5. get_user_roles: returns all roles for a user as array
CREATE OR REPLACE FUNCTION public.get_user_roles(_user_id uuid)
RETURNS app_role[]
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT array_agg(role ORDER BY role) FROM public.user_roles WHERE user_id = _user_id
$$;

-- 6. get_user_permissions: returns all permissions for a user via their roles
CREATE OR REPLACE FUNCTION public.get_user_permissions(_user_id uuid)
RETURNS app_permission[]
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT array_agg(DISTINCT rp.permission ORDER BY rp.permission)
  FROM public.user_roles ur
  JOIN public.role_permissions rp ON rp.role = ur.role
  WHERE ur.user_id = _user_id
$$;
