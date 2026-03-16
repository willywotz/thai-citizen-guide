import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders, corsResponse, jsonResponse, errorResponse } from '../_shared/cors.ts';
import { authenticateRequest, checkPermission } from '../_shared/auth.ts';

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const adminAuthClient = createClient(supabaseUrl, serviceRoleKey).auth.admin;

// Roles that require super_admin to assign
const PRIVILEGED_ROLES = ['super_admin', 'admin'];

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return corsResponse();

  const auth = await authenticateRequest(req);
  if (!auth) return errorResponse('Unauthorized', 401);

  const adminClient = createClient(supabaseUrl, serviceRoleKey);
  const url = new URL(req.url);

  // GET /manage-users — list all users with profiles and roles
  if (req.method === 'GET') {
    const canRead = await checkPermission(auth, 'users.read');
    if (!canRead) return errorResponse('Forbidden', 403);

    const userId = url.searchParams.get('user_id');

    if (userId) {
      // Get single user
      const [authUser, profileRes, rolesRes, apiKeyCountRes] = await Promise.all([
        adminAuthClient.getUserById(userId),
        adminClient.from('profiles').select('*').eq('id', userId).single(),
        adminClient.from('user_roles').select('role').eq('user_id', userId),
        adminClient.from('api_keys').select('id', { count: 'exact', head: true }).eq('user_id', userId).is('revoked_at', null),
      ]);

      if (authUser.error) return errorResponse('User not found', 404);

      return jsonResponse({
        data: {
          id: userId,
          email: authUser.data.user.email,
          profile: profileRes.data,
          roles: (rolesRes.data ?? []).map((r: { role: string }) => r.role),
          api_key_count: apiKeyCountRes.count ?? 0,
          last_sign_in_at: authUser.data.user.last_sign_in_at,
          created_at: authUser.data.user.created_at,
        },
      });
    }

    // List all users
    const page = parseInt(url.searchParams.get('page') ?? '1');
    const perPage = Math.min(parseInt(url.searchParams.get('per_page') ?? '50'), 100);
    const search = url.searchParams.get('search') ?? '';

    const { data: authUsers, error: authError } = await adminAuthClient.listUsers({ page, perPage });
    if (authError) return errorResponse(authError.message, 500);

    const userIds = authUsers.users.map((u) => u.id);

    const [profilesRes, rolesRes] = await Promise.all([
      adminClient.from('profiles').select('*').in('id', userIds),
      adminClient.from('user_roles').select('user_id, role').in('user_id', userIds),
    ]);

    const profileMap = Object.fromEntries((profilesRes.data ?? []).map((p: { id: string }) => [p.id, p]));
    const rolesMap: Record<string, string[]> = {};
    for (const r of (rolesRes.data ?? []) as { user_id: string; role: string }[]) {
      if (!rolesMap[r.user_id]) rolesMap[r.user_id] = [];
      rolesMap[r.user_id].push(r.role);
    }

    let users = authUsers.users.map((u) => ({
      id: u.id,
      email: u.email,
      profile: profileMap[u.id] ?? null,
      roles: rolesMap[u.id] ?? [],
      last_sign_in_at: u.last_sign_in_at,
      created_at: u.created_at,
    }));

    // Simple email/name search filter
    if (search) {
      const q = search.toLowerCase();
      users = users.filter(
        (u) =>
          u.email?.toLowerCase().includes(q) ||
          (u.profile as any)?.display_name?.toLowerCase().includes(q)
      );
    }

    return jsonResponse({ data: users, total: authUsers.total });
  }

  // PUT /manage-users — update user (assign role / deactivate)
  if (req.method === 'PUT') {
    const body = await req.json();
    const { action, user_id, role, is_active, display_name } = body as {
      action: 'assign_role' | 'remove_role' | 'deactivate' | 'activate' | 'update_profile';
      user_id: string;
      role?: string;
      is_active?: boolean;
      display_name?: string;
    };

    if (!user_id) return errorResponse('user_id required');

    if (action === 'assign_role' || action === 'remove_role') {
      const canAssign = await checkPermission(auth, 'users.roles.assign');
      if (!canAssign) return errorResponse('Forbidden', 403);

      if (!role) return errorResponse('role required');

      // Only super_admin can assign privileged roles
      if (PRIVILEGED_ROLES.includes(role) && !auth.roles.includes('super_admin')) {
        return errorResponse('Only super_admin can assign admin/super_admin roles', 403);
      }

      if (action === 'assign_role') {
        const { error } = await adminClient
          .from('user_roles')
          .upsert({ user_id, role }, { onConflict: 'user_id,role' });
        if (error) return errorResponse(error.message, 500);
      } else {
        const { error } = await adminClient
          .from('user_roles')
          .delete()
          .eq('user_id', user_id)
          .eq('role', role);
        if (error) return errorResponse(error.message, 500);
      }

      return jsonResponse({ success: true });
    }

    if (action === 'deactivate' || action === 'activate') {
      const canWrite = await checkPermission(auth, 'users.write');
      if (!canWrite) return errorResponse('Forbidden', 403);

      const active = action === 'activate';
      const { error } = await adminClient
        .from('profiles')
        .update({ is_active: active, updated_at: new Date().toISOString() })
        .eq('id', user_id);

      if (error) return errorResponse(error.message, 500);
      return jsonResponse({ success: true });
    }

    if (action === 'update_profile') {
      const canWrite = await checkPermission(auth, 'users.write');
      const isSelf = auth.userId === user_id;
      if (!canWrite && !isSelf) return errorResponse('Forbidden', 403);

      const updates: Record<string, unknown> = { updated_at: new Date().toISOString() };
      if (display_name !== undefined) updates.display_name = display_name;

      const { error } = await adminClient
        .from('profiles')
        .update(updates)
        .eq('id', user_id);

      if (error) return errorResponse(error.message, 500);
      return jsonResponse({ success: true });
    }

    return errorResponse('Unknown action');
  }

  // DELETE /manage-users?user_id=<uuid> — delete user (super_admin only)
  if (req.method === 'DELETE') {
    const canDelete = await checkPermission(auth, 'users.delete');
    if (!canDelete) return errorResponse('Forbidden', 403);

    const userId = url.searchParams.get('user_id');
    if (!userId) return errorResponse('user_id required');

    // Prevent self-deletion
    if (userId === auth.userId) return errorResponse('Cannot delete own account via this endpoint');

    const { error } = await adminAuthClient.deleteUser(userId);
    if (error) return errorResponse(error.message, 500);

    return jsonResponse({ success: true });
  }

  return errorResponse('Method not allowed', 405);
});
