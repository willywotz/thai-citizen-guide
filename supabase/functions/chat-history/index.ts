const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const mockHistory = [
  {
    id: 'conv-1',
    title: 'ตรวจสอบทะเบียนยาพาราเซตามอล',
    preview: 'ยาพาราเซตามอลที่ขายตามร้านขายยาทั่วไป ต้องขึ้นทะเบียนกับ อย. หรือไม่?',
    date: '2568-02-22',
    agencies: ['อย.', 'กรมสรรพากร'],
    status: 'success',
    messageCount: 4,
    responseTime: '2.1 วินาที',
  },
  {
    id: 'conv-2',
    title: 'สอบถามเรื่องลดหย่อนภาษี',
    preview: 'ค่าลดหย่อนภาษีเงินได้บุคคลธรรมดาปี 2568 มีอะไรบ้าง?',
    date: '2568-02-21',
    agencies: ['กรมสรรพากร'],
    status: 'success',
    messageCount: 2,
    responseTime: '1.8 วินาที',
  },
  {
    id: 'conv-3',
    title: 'ขั้นตอนทำบัตรประชาชนใหม่',
    preview: 'บัตรประชาชนหาย ต้องทำอย่างไร ใช้เอกสารอะไรบ้าง?',
    date: '2568-02-20',
    agencies: ['กรมการปกครอง'],
    status: 'success',
    messageCount: 3,
    responseTime: '2.5 วินาที',
  },
  {
    id: 'conv-4',
    title: 'ราคาประเมินที่ดิน กรุงเทพ',
    preview: 'ตรวจสอบราคาประเมินที่ดินในเขตบางรัก กรุงเทพมหานคร',
    date: '2568-02-19',
    agencies: ['กรมที่ดิน'],
    status: 'success',
    messageCount: 2,
    responseTime: '1.9 วินาที',
  },
  {
    id: 'conv-5',
    title: 'นำเข้าอาหารเสริม',
    preview: 'ขั้นตอนการนำเข้าอาหารเสริมจากต่างประเทศ ต้องขออนุญาตจากหน่วยงานใดบ้าง?',
    date: '2568-02-18',
    agencies: ['อย.', 'กรมสรรพากร'],
    status: 'failed',
    messageCount: 1,
    responseTime: '5.2 วินาที',
  },
  {
    id: 'conv-6',
    title: 'การจดทะเบียนโอนที่ดิน',
    preview: 'ต้องเตรียมเอกสารอะไรบ้างในการโอนที่ดิน และค่าธรรมเนียมเท่าไร?',
    date: '2568-02-17',
    agencies: ['กรมที่ดิน', 'กรมสรรพากร'],
    status: 'success',
    messageCount: 6,
    responseTime: '3.1 วินาที',
  },
  {
    id: 'conv-7',
    title: 'เปลี่ยนชื่อสกุลหลังสมรส',
    preview: 'ขั้นตอนการเปลี่ยนชื่อสกุลหลังจดทะเบียนสมรส ใช้เอกสารอะไรบ้าง?',
    date: '2568-02-16',
    agencies: ['กรมการปกครอง'],
    status: 'success',
    messageCount: 4,
    responseTime: '2.0 วินาที',
  },
  {
    id: 'conv-8',
    title: 'ตรวจสอบเลข อย. อาหารเสริม',
    preview: 'จะตรวจสอบว่าอาหารเสริมที่ซื้อมามีเลข อย. จริงหรือไม่ ทำอย่างไร?',
    date: '2568-02-15',
    agencies: ['อย.'],
    status: 'success',
    messageCount: 3,
    responseTime: '1.5 วินาที',
  },
];

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const start = Date.now();

  await new Promise((r) => setTimeout(r, 150 + Math.random() * 200));

  // Parse optional query params from body
  let search = '';
  let filterAgency = '';
  try {
    const body = await req.json();
    search = body.search || '';
    filterAgency = body.filterAgency || '';
  } catch {
    // GET request or no body — return all
  }

  let filtered = mockHistory;
  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (c) => c.title.toLowerCase().includes(q) || c.preview.toLowerCase().includes(q)
    );
  }
  if (filterAgency) {
    filtered = filtered.filter((c) => c.agencies.includes(filterAgency));
  }

  return new Response(
    JSON.stringify({
      success: true,
      data: filtered,
      total: mockHistory.length,
      responseTime: Date.now() - start,
    }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
});
