import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { corsHeaders, corsResponse } from '../_shared/cors.ts';
import { authenticateRequest, checkPermission } from '../_shared/auth.ts';

const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return corsResponse();

  const auth = await authenticateRequest(req);
  if (!auth) {
    return new Response(
      JSON.stringify({ success: false, error: 'Unauthorized' }),
      { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }

  const start = Date.now();
  const supabase = createClient(supabaseUrl, supabaseKey);

  let search = '';
  let filterAgency = '';
  try {
    const body = await req.json();
    search = body.search || '';
    filterAgency = body.filterAgency || '';
  } catch {
    // no body
  }

  const canReadAll = await checkPermission(auth, 'conversations.read.all');

  let query = supabase
    .from('conversations')
    .select('*')
    .order('created_at', { ascending: false });

  // Non-admins only see their own conversations
  if (!canReadAll) {
    query = query.eq('user_id', auth.userId);
  }

  if (search) {
    query = query.or(`title.ilike.%${search}%,preview.ilike.%${search}%`);
  }
  if (filterAgency) {
    query = query.contains('agencies', [filterAgency]);
  }

  const { data, error } = await query;

  if (error) {
    return new Response(
      JSON.stringify({ success: false, error: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }

  return new Response(
    JSON.stringify({
      success: true,
      data: (data || []).map((c: any) => ({
        id: c.id,
        title: c.title,
        preview: c.preview,
        date: c.created_at?.split('T')[0] || '',
        agencies: c.agencies || [],
        status: c.status || 'success',
        messageCount: c.message_count || 0,
        responseTime: c.response_time || '',
      })),
      total: data?.length || 0,
      responseTime: Date.now() - start,
    }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
});
