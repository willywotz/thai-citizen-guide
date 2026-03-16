import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

export interface AuthResult {
  userId: string;
  roles: string[];
  authMethod: 'jwt' | 'api_key';
}

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

/**
 * Authenticates a request via JWT bearer token or x-api-key header.
 * Returns null if not authenticated.
 */
export async function authenticateRequest(req: Request): Promise<AuthResult | null> {
  const apiKeyHeader = req.headers.get('x-api-key');
  const authHeader = req.headers.get('Authorization');

  // --- API Key auth ---
  if (apiKeyHeader) {
    return validateApiKey(apiKeyHeader, req);
  }

  // --- JWT auth ---
  if (authHeader?.startsWith('Bearer ')) {
    return validateJwt(authHeader.slice(7));
  }

  return null;
}

async function validateJwt(token: string): Promise<AuthResult | null> {
  try {
    const client = createClient(supabaseUrl, token);
    const { data: { user }, error } = await client.auth.getUser();
    if (error || !user) return null;

    // Prefer JWT claims for roles (faster); fall back to DB query
    const anonClient = createClient(supabaseUrl, serviceRoleKey);
    const { data: roleRows } = await anonClient
      .from('user_roles')
      .select('role')
      .eq('user_id', user.id);

    const roles = (roleRows ?? []).map((r: { role: string }) => r.role);
    return { userId: user.id, roles, authMethod: 'jwt' };
  } catch {
    return null;
  }
}

async function validateApiKey(rawKey: string, req: Request): Promise<AuthResult | null> {
  try {
    const keyHash = await sha256(rawKey);
    const adminClient = createClient(supabaseUrl, serviceRoleKey);

    const { data: keyRow, error } = await adminClient
      .from('api_keys')
      .select('id, user_id, scopes, expires_at, revoked_at')
      .eq('key_hash', keyHash)
      .is('revoked_at', null)
      .single();

    if (error || !keyRow) return null;

    // Check expiry
    if (keyRow.expires_at && new Date(keyRow.expires_at) < new Date()) return null;

    // Update last_used_at async (don't await)
    const ip = req.headers.get('x-forwarded-for') ?? req.headers.get('cf-connecting-ip') ?? null;
    adminClient
      .from('api_keys')
      .update({ last_used_at: new Date().toISOString(), last_used_ip: ip, updated_at: new Date().toISOString() })
      .eq('id', keyRow.id)
      .then(() => {});

    return {
      userId: keyRow.user_id,
      roles: ['api_user'],
      authMethod: 'api_key',
    };
  } catch {
    return null;
  }
}

async function sha256(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Checks if the auth result has a required permission via role_permissions table.
 */
export async function checkPermission(auth: AuthResult, permission: string): Promise<boolean> {
  const adminClient = createClient(supabaseUrl, serviceRoleKey);
  const { data } = await adminClient
    .from('role_permissions')
    .select('permission')
    .in('role', auth.roles)
    .eq('permission', permission)
    .limit(1);
  return (data?.length ?? 0) > 0;
}

/**
 * Generates a cryptographically random API key with a given prefix.
 * Returns { rawKey, keyHash, keyPrefix }.
 */
export async function generateApiKey(prefix = 'tcg_live_'): Promise<{
  rawKey: string;
  keyHash: string;
  keyPrefix: string;
}> {
  const randomBytes = new Uint8Array(32);
  crypto.getRandomValues(randomBytes);
  const base64 = btoa(String.fromCharCode(...randomBytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
  const rawKey = prefix + base64;
  const keyHash = await sha256(rawKey);
  const keyPrefix = rawKey.slice(0, 20);
  return { rawKey, keyHash, keyPrefix };
}
