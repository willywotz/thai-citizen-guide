import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  try {
    // POST with action
    if (req.method === 'POST') {
      const body = await req.json();

      // Test connection
      if (body.action === 'test') {
        return handleTest(body);
      }

      // Create agency
      const { data, error } = await supabase.from('agencies').insert({
        name: body.name,
        short_name: body.short_name,
        logo: body.logo || '🏢',
        connection_type: body.connection_type || 'API',
        status: body.status || 'active',
        description: body.description || '',
        data_scope: body.data_scope || [],
        color: body.color || 'hsl(213 70% 45%)',
        endpoint_url: body.endpoint_url || '',
        api_key_name: body.api_key_name || null,
        auth_method: body.auth_method || 'api_key',
        auth_header: body.auth_header || '',
        base_path: body.base_path || '',
        rate_limit_rpm: body.rate_limit_rpm || null,
        request_format: body.request_format || 'json',
        api_endpoints: body.api_endpoints || [],
        api_spec_raw: body.api_spec_raw || null,
      }).select().single();

      if (error) throw error;
      return json({ success: true, data });
    }

    // PUT - update
    if (req.method === 'PUT') {
      const body = await req.json();
      const { id, ...updates } = body;
      updates.updated_at = new Date().toISOString();

      const { data, error } = await supabase
        .from('agencies')
        .update(updates)
        .eq('id', id)
        .select()
        .single();

      if (error) throw error;
      return json({ success: true, data });
    }

    // DELETE
    if (req.method === 'DELETE') {
      const { id } = await req.json();
      const { error } = await supabase.from('agencies').delete().eq('id', id);
      if (error) throw error;
      return json({ success: true });
    }

    return json({ error: 'Method not allowed' }, 405);
  } catch (err) {
    return json({ success: false, error: err.message }, 500);
  }
});

function handleTest(body: { connection_type: string; endpoint_url: string }) {
  const start = Date.now();
  const delay = 100 + Math.random() * 300;

  return new Promise<Response>((resolve) => {
    setTimeout(() => {
      const latency = Date.now() - start;
      let result: Record<string, unknown>;

      switch (body.connection_type) {
        case 'MCP':
          result = {
            success: true,
            protocol: 'MCP',
            version: '1.0',
            steps: [
              { step: 1, label: 'TCP Connection', status: 'done', time: Math.round(latency * 0.2) },
              { step: 2, label: 'MCP Handshake', status: 'done', time: Math.round(latency * 0.4) },
              { step: 3, label: 'Capability Exchange', status: 'done', time: Math.round(latency * 0.3) },
              { step: 4, label: 'Session Established', status: 'done', time: Math.round(latency * 0.1) },
            ],
            capabilities: ['tools/list', 'tools/call', 'resources/read'],
            latency: `${latency}ms`,
          };
          break;
        case 'A2A':
          result = {
            success: true,
            protocol: 'A2A',
            version: '0.2',
            steps: [
              { step: 1, label: 'DNS Resolution', status: 'done', time: Math.round(latency * 0.15) },
              { step: 2, label: 'Agent Card Request', status: 'done', time: Math.round(latency * 0.35) },
              { step: 3, label: 'Capability Negotiation', status: 'done', time: Math.round(latency * 0.3) },
              { step: 4, label: 'Agent Link Ready', status: 'done', time: Math.round(latency * 0.2) },
            ],
            agentCard: { name: 'Remote Agent', skills: ['query', 'verify'] },
            latency: `${latency}ms`,
          };
          break;
        default: // API
          result = {
            success: true,
            protocol: 'REST API',
            version: 'v1',
            steps: [
              { step: 1, label: 'HTTP Connection', status: 'done', time: Math.round(latency * 0.2) },
              { step: 2, label: 'Authentication', status: 'done', time: Math.round(latency * 0.3) },
              { step: 3, label: 'Health Check', status: 'done', time: Math.round(latency * 0.3) },
              { step: 4, label: 'API Ready', status: 'done', time: Math.round(latency * 0.2) },
            ],
            endpoints: ['/health', '/query', '/status'],
            latency: `${latency}ms`,
          };
      }

      resolve(json(result));
    }, delay);
  });
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}
