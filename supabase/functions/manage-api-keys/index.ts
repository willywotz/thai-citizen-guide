import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders, corsResponse, jsonResponse, errorResponse } from '../_shared/cors.ts';
import { authenticateRequest, checkPermission, generateApiKey } from '../_shared/auth.ts';

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return corsResponse();

  const auth = await authenticateRequest(req);
  if (!auth) return errorResponse('Unauthorized', 401);

  const adminClient = createClient(supabaseUrl, serviceRoleKey);
  const url = new URL(req.url);

  // GET /manage-api-keys — list keys
  if (req.method === 'GET') {
    const listAll = url.searchParams.get('all') === 'true';

    if (listAll) {
      const canReadAll = await checkPermission(auth, 'api_keys.read.all');
      if (!canReadAll) return errorResponse('Forbidden', 403);

      const { data, error } = await adminClient
        .from('api_keys')
        .select('id, user_id, name, key_prefix, scopes, expires_at, last_used_at, revoked_at, created_at')
        .order('created_at', { ascending: false });

      if (error) return errorResponse(error.message, 500);
      return jsonResponse({ data });
    }

    // List own keys
    const { data, error } = await adminClient
      .from('api_keys')
      .select('id, name, key_prefix, scopes, expires_at, last_used_at, revoked_at, created_at')
      .eq('user_id', auth.userId)
      .order('created_at', { ascending: false });

    if (error) return errorResponse(error.message, 500);
    return jsonResponse({ data });
  }

  // POST /manage-api-keys — create a new key
  if (req.method === 'POST') {
    const canWrite = await checkPermission(auth, 'api_keys.write.own');
    if (!canWrite) return errorResponse('Forbidden', 403);

    const body = await req.json();
    const { name, scopes, expires_at } = body as {
      name: string;
      scopes: string[];
      expires_at?: string | null;
    };

    if (!name?.trim()) return errorResponse('name is required');
    if (!Array.isArray(scopes)) return errorResponse('scopes must be an array');

    const { rawKey, keyHash, keyPrefix } = await generateApiKey('tcg_live_');

    const { data, error } = await adminClient
      .from('api_keys')
      .insert({
        user_id: auth.userId,
        name: name.trim(),
        key_prefix: keyPrefix,
        key_hash: keyHash,
        scopes,
        expires_at: expires_at ?? null,
      })
      .select('id, name, key_prefix, scopes, expires_at, created_at')
      .single();

    if (error) return errorResponse(error.message, 500);

    return jsonResponse({ data: { ...data, raw_key: rawKey } }, 201);
  }

  // DELETE /manage-api-keys?id=<uuid> — revoke a key
  if (req.method === 'DELETE') {
    const keyId = url.searchParams.get('id');
    if (!keyId) return errorResponse('id query param required');

    // Check ownership or revoke.all permission
    const { data: keyRow } = await adminClient
      .from('api_keys')
      .select('user_id, revoked_at')
      .eq('id', keyId)
      .single();

    if (!keyRow) return errorResponse('Key not found', 404);

    const canRevokeAll = await checkPermission(auth, 'api_keys.revoke.all');
    const isOwner = keyRow.user_id === auth.userId;

    if (!isOwner && !canRevokeAll) return errorResponse('Forbidden', 403);
    if (keyRow.revoked_at) return errorResponse('Key already revoked');

    const reason = url.searchParams.get('reason') ?? 'user_request';
    const { error } = await adminClient
      .from('api_keys')
      .update({
        revoked_at: new Date().toISOString(),
        revoked_reason: reason,
        updated_at: new Date().toISOString(),
      })
      .eq('id', keyId);

    if (error) return errorResponse(error.message, 500);
    return jsonResponse({ success: true });
  }

  return errorResponse('Method not allowed', 405);
});
