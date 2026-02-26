const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const start = Date.now();

  await new Promise((r) => setTimeout(r, 150 + Math.random() * 200));

  const agencies = [
    {
      id: 'fda',
      name: 'สำนักงานคณะกรรมการอาหารและยา',
      shortName: 'อย.',
      logo: '🏥',
      connectionType: 'MCP',
      status: 'active',
      description: 'ระบบตรวจสอบทะเบียนยา อาหาร เครื่องสำอาง และผลิตภัณฑ์สุขภาพ',
      dataScope: ['ทะเบียนยา', 'ทะเบียนอาหาร', 'เครื่องสำอาง', 'ผลิตภัณฑ์สุขภาพ', 'การขออนุญาต'],
      totalCalls: 12450 + Math.floor(Math.random() * 100),
      color: 'hsl(145 55% 40%)',
      lastPing: Date.now() - Math.floor(Math.random() * 5000),
      uptime: parseFloat((99.5 + Math.random() * 0.4).toFixed(2)),
    },
    {
      id: 'revenue',
      name: 'กรมสรรพากร',
      shortName: 'กรมสรรพากร',
      logo: '💰',
      connectionType: 'API',
      status: 'active',
      description: 'ระบบสอบถามข้อมูลภาษี การยื่นแบบ และสิทธิประโยชน์ทางภาษี',
      dataScope: ['ภาษีเงินได้บุคคลธรรมดา', 'ภาษีนิติบุคคล', 'ภาษีมูลค่าเพิ่ม', 'การยื่นแบบ', 'สิทธิลดหย่อน'],
      totalCalls: 18320 + Math.floor(Math.random() * 100),
      color: 'hsl(213 70% 45%)',
      lastPing: Date.now() - Math.floor(Math.random() * 5000),
      uptime: parseFloat((99.2 + Math.random() * 0.7).toFixed(2)),
    },
    {
      id: 'dopa',
      name: 'กรมการปกครอง',
      shortName: 'กรมการปกครอง',
      logo: '🏛️',
      connectionType: 'A2A',
      status: 'active',
      description: 'ระบบตรวจสอบข้อมูลทะเบียนราษฎร์ บัตรประชาชน และงานปกครอง',
      dataScope: ['ทะเบียนราษฎร์', 'บัตรประจำตัวประชาชน', 'ทะเบียนบ้าน', 'การเปลี่ยนชื่อ', 'สถานะบุคคล'],
      totalCalls: 9870 + Math.floor(Math.random() * 100),
      color: 'hsl(25 85% 55%)',
      lastPing: Date.now() - Math.floor(Math.random() * 5000),
      uptime: parseFloat((98.8 + Math.random() * 1.0).toFixed(2)),
    },
    {
      id: 'land',
      name: 'กรมที่ดิน',
      shortName: 'กรมที่ดิน',
      logo: '🗺️',
      connectionType: 'MCP',
      status: 'active',
      description: 'ระบบสอบถามข้อมูลที่ดิน โฉนด การจดทะเบียนสิทธิและนิติกรรม',
      dataScope: ['โฉนดที่ดิน', 'การจดทะเบียน', 'ราคาประเมิน', 'การรังวัด', 'สิทธิและนิติกรรม'],
      totalCalls: 7650 + Math.floor(Math.random() * 100),
      color: 'hsl(280 50% 50%)',
      lastPing: Date.now() - Math.floor(Math.random() * 5000),
      uptime: parseFloat((99.0 + Math.random() * 0.9).toFixed(2)),
    },
  ];

  return new Response(
    JSON.stringify({
      success: true,
      data: agencies,
      responseTime: Date.now() - start,
    }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
});
