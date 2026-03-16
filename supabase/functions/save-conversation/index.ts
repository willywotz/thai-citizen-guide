import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders, corsResponse } from '../_shared/cors.ts';
import { authenticateRequest } from '../_shared/auth.ts';

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return corsResponse();

  const supabase = createClient(supabaseUrl, supabaseKey);

  // Auth is optional — authenticated users own their conversations,
  // unauthenticated (public portal) conversations become public
  const auth = await authenticateRequest(req);

  try {
    const body = await req.json();
    const { title, preview, agencies, status, responseTime, messages } = body;

    const { data: conv, error: convError } = await supabase
      .from('conversations')
      .insert({
        title: title || 'สนทนาใหม่',
        preview: preview || '',
        agencies: agencies || [],
        status: status || 'success',
        message_count: messages?.length || 0,
        response_time: responseTime || null,
        user_id: auth?.userId ?? null,
        is_public: !auth,          // public portal conversations are public
      })
      .select('id')
      .single();

    if (convError) throw convError;

    if (messages && messages.length > 0) {
      const rows = messages.map((m: any) => ({
        id: m.id || undefined,
        conversation_id: conv.id,
        role: m.role,
        content: m.content,
        agent_steps: m.agentSteps || null,
        sources: m.sources || null,
        rating: m.rating || null,
      }));

      const { error: msgError } = await supabase.from('messages').insert(rows);
      if (msgError) throw msgError;
    }

    return new Response(
      JSON.stringify({ success: true, conversationId: conv.id }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (err: any) {
    return new Response(
      JSON.stringify({ success: false, error: err.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
