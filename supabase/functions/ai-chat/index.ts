const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface AgencyResult {
  success: boolean;
  agency: string;
  agencyName: string;
  data: {
    answer: string;
    references: { title: string; url: string }[];
    confidence: number;
  };
  responseTime: number;
}

// Keyword-based agency routing
function detectAgencies(query: string): string[] {
  const q = query.toLowerCase();
  const matched: string[] = [];

  if (q.includes('ยา') || q.includes('อาหาร') || q.includes('เครื่องสำอาง') || q.includes('อย.') || q.includes('พาราเซตามอล') || q.includes('นำเข้า') || q.includes('ผลิตภัณฑ์สุขภาพ')) {
    matched.push('fda');
  }
  if (q.includes('ภาษี') || q.includes('ลดหย่อน') || q.includes('สรรพากร') || q.includes('vat') || q.includes('ยื่นแบบ') || q.includes('เงินได้')) {
    matched.push('revenue');
  }
  if (q.includes('บัตรประชาชน') || q.includes('ทะเบียนราษฎร์') || q.includes('ทะเบียนบ้าน') || q.includes('ปกครอง') || q.includes('เปลี่ยนชื่อ') || q.includes('แจ้งเกิด')) {
    matched.push('dopa');
  }
  if (q.includes('ที่ดิน') || q.includes('โฉนด') || q.includes('ราคาประเมิน') || q.includes('จดทะเบียน') || q.includes('รังวัด') || q.includes('โอนที่ดิน')) {
    matched.push('land');
  }

  // Default: pick fda if nothing matched
  if (matched.length === 0) matched.push('fda');

  return matched;
}

const agencyFunctionMap: Record<string, string> = {
  fda: 'agency-fda',
  revenue: 'agency-revenue',
  dopa: 'agency-dopa',
  land: 'agency-land',
};

const agencyNameMap: Record<string, string> = {
  fda: 'สำนักงาน อย.',
  revenue: 'กรมสรรพากร',
  dopa: 'กรมการปกครอง',
  land: 'กรมที่ดิน',
};

const agencyIconMap: Record<string, string> = {
  fda: '🏥',
  revenue: '💰',
  dopa: '🏛️',
  land: '🗺️',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const start = Date.now();

  try {
    const { query } = await req.json();
    if (!query || typeof query !== 'string') {
      return new Response(
        JSON.stringify({ success: false, error: 'Missing query parameter' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Step 1: Detect relevant agencies
    const targetAgencies = detectAgencies(query);

    // Step 2: Build agent steps
    const agentSteps = [
      { icon: '🔍', label: 'กำลังวิเคราะห์คำถาม...', status: 'done' },
      { icon: '📋', label: `วางแผนการสืบค้น → เลือกหน่วยงาน: ${targetAgencies.map(a => agencyNameMap[a]).join(', ')}`, status: 'done' },
    ];

    // Step 3: Call agency functions in parallel
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_ANON_KEY')!;

    const agencyPromises = targetAgencies.map(async (agencyId) => {
      const fnName = agencyFunctionMap[agencyId];
      agentSteps.push({
        icon: '🔗',
        label: `กำลังสืบค้นจาก ${agencyNameMap[agencyId]} ...`,
        status: 'done',
      });

      try {
        const res = await fetch(`${supabaseUrl}/functions/v1/${fnName}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${supabaseKey}`,
          },
          body: JSON.stringify({ query }),
        });
        return (await res.json()) as AgencyResult;
      } catch {
        return null;
      }
    });

    const results = (await Promise.all(agencyPromises)).filter(Boolean) as AgencyResult[];

    agentSteps.push(
      { icon: '✅', label: 'รวบรวมและประเมินผลลัพธ์', status: 'done' },
      { icon: '📝', label: 'สังเคราะห์คำตอบ', status: 'done' },
    );

    // Step 4: Synthesize answer
    const combinedAnswer = results.map((r) => r.data.answer).join('\n\n---\n\n');
    const allReferences = results.flatMap((r) =>
      r.data.references.map((ref) => ({
        agency: r.agencyName,
        ...ref,
      }))
    );

    return new Response(
      JSON.stringify({
        success: true,
        data: {
          answer: combinedAnswer,
          references: allReferences,
          agentSteps,
          agencies: targetAgencies.map((id) => ({
            id,
            name: agencyNameMap[id],
            icon: agencyIconMap[id],
          })),
          confidence: results.reduce((sum, r) => sum + r.data.confidence, 0) / results.length,
        },
        responseTime: Date.now() - start,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ success: false, error: String(error) }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
