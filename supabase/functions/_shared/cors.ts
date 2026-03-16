export const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers':
    'authorization, x-client-info, apikey, content-type, x-api-key, ' +
    'x-supabase-client-platform, x-supabase-client-platform-version, ' +
    'x-supabase-client-runtime, x-supabase-client-runtime-version',
};

export function corsResponse() {
  return new Response('ok', { headers: corsHeaders });
}

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

export function errorResponse(message: string, status = 400) {
  return jsonResponse({ error: message }, status);
}
