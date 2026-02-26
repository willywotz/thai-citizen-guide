import type { Agency, AgentStep, ChatMessage, ConversationHistory, DashboardStats } from '@/types';

// Re-export types for backward compatibility
export type { Agency, AgentStep, ChatMessage, ConversationHistory, DashboardStats };

// ===== Mock Data =====

export const agencies: Agency[] = [
  {
    id: 'fda',
    name: 'สำนักงานคณะกรรมการอาหารและยา',
    shortName: 'อย.',
    logo: '🏥',
    connectionType: 'MCP',
    status: 'active',
    description: 'ระบบตรวจสอบทะเบียนยา อาหาร เครื่องสำอาง และผลิตภัณฑ์สุขภาพ',
    dataScope: ['ทะเบียนยา', 'ทะเบียนอาหาร', 'เครื่องสำอาง', 'ผลิตภัณฑ์สุขภาพ', 'การขออนุญาต'],
    totalCalls: 12450,
    color: 'hsl(145 55% 40%)',
    endpointUrl: 'https://api.fda.moph.go.th/mcp',
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
    totalCalls: 18320,
    color: 'hsl(213 70% 45%)',
    endpointUrl: 'https://api.rd.go.th/v1',
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
    totalCalls: 9870,
    color: 'hsl(25 85% 55%)',
    endpointUrl: 'https://api.dopa.go.th/a2a',
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
    totalCalls: 7650,
    color: 'hsl(280 50% 50%)',
    endpointUrl: 'https://api.dol.go.th/mcp',
  },
];

export const suggestedQuestions = [
  'ขอตรวจสอบทะเบียนยา พาราเซตามอล',
  'สอบถามเรื่องการลดหย่อนภาษี 2568',
  'ขั้นตอนการทำบัตรประชาชนใหม่',
  'ตรวจสอบราคาประเมินที่ดิน กรุงเทพฯ',
];

export const mockAgentSteps: AgentStep[] = [
  { icon: '🔍', label: 'กำลังวิเคราะห์คำถาม...', status: 'done' },
  { icon: '📋', label: 'วางแผนการสืบค้น → เลือกหน่วยงาน: อย., กรมสรรพากร', status: 'done' },
  { icon: '🔗', label: 'กำลังสืบค้นจาก สำนักงาน อย. ...', status: 'done' },
  { icon: '🔗', label: 'กำลังสืบค้นจาก กรมสรรพากร ...', status: 'done' },
  { icon: '✅', label: 'รวบรวมและประเมินผลลัพธ์', status: 'done' },
  { icon: '📝', label: 'สังเคราะห์คำตอบ', status: 'done' },
];

export const mockConversation: ChatMessage[] = [
  {
    id: '1',
    role: 'user',
    content: 'ยาพาราเซตามอลที่ขายตามร้านขายยาทั่วไป ต้องขึ้นทะเบียนกับ อย. หรือไม่? และมีภาษีอะไรที่เกี่ยวข้องบ้าง?',
    timestamp: '10:30',
  },
  {
    id: '2',
    role: 'assistant',
    content: `**การขึ้นทะเบียนยาพาราเซตามอลกับ อย.**\n\nยาพาราเซตามอลที่จำหน่ายในประเทศไทยทุกตัว **ต้องขึ้นทะเบียนกับสำนักงานคณะกรรมการอาหารและยา (อย.)** ตาม พ.ร.บ. ยา พ.ศ. 2510 โดยจัดเป็น "ยาสามัญประจำบ้าน" หรือ "ยาอันตราย" ขึ้นอยู่กับสูตรและความเข้มข้น\n\n**ภาษีที่เกี่ยวข้อง:**\n- ภาษีมูลค่าเพิ่ม (VAT) 7% สำหรับการจำหน่าย\n- ภาษีเงินได้นิติบุคคลสำหรับผู้ผลิต/ผู้นำเข้า\n- ยาพาราเซตามอลได้รับยกเว้นภาษีสรรพสามิต`,
    timestamp: '10:31',
    agentSteps: mockAgentSteps,
    sources: [
      { agency: 'สำนักงาน อย.', url: 'https://www.fda.moph.go.th', title: 'ระบบตรวจสอบทะเบียนยา' },
      { agency: 'กรมสรรพากร', url: 'https://www.rd.go.th', title: 'อัตราภาษีมูลค่าเพิ่ม' },
    ],
  },
];

export const conversationHistory: ConversationHistory[] = [
  {
    id: 'conv-1',
    title: 'ตรวจสอบทะเบียนยาพาราเซตามอล',
    preview: 'ยาพาราเซตามอลที่ขายตามร้านขายยาทั่วไป ต้องขึ้นทะเบียนกับ อย. หรือไม่?',
    date: '2568-02-22',
    agencies: ['อย.', 'กรมสรรพากร'],
    status: 'success',
    messages: mockConversation,
  },
  {
    id: 'conv-2',
    title: 'สอบถามเรื่องลดหย่อนภาษี',
    preview: 'ค่าลดหย่อนภาษีเงินได้บุคคลธรรมดาปี 2568 มีอะไรบ้าง?',
    date: '2568-02-21',
    agencies: ['กรมสรรพากร'],
    status: 'success',
    messages: [],
  },
  {
    id: 'conv-3',
    title: 'ขั้นตอนทำบัตรประชาชนใหม่',
    preview: 'บัตรประชาชนหาย ต้องทำอย่างไร ใช้เอกสารอะไรบ้าง?',
    date: '2568-02-20',
    agencies: ['กรมการปกครอง'],
    status: 'success',
    messages: [],
  },
  {
    id: 'conv-4',
    title: 'ราคาประเมินที่ดิน กรุงเทพ',
    preview: 'ตรวจสอบราคาประเมินที่ดินในเขตบางรัก กรุงเทพมหานคร',
    date: '2568-02-19',
    agencies: ['กรมที่ดิน'],
    status: 'success',
    messages: [],
  },
  {
    id: 'conv-5',
    title: 'นำเข้าอาหารเสริม',
    preview: 'ขั้นตอนการนำเข้าอาหารเสริมจากต่างประเทศ ต้องขออนุญาตจากหน่วยงานใดบ้าง?',
    date: '2568-02-18',
    agencies: ['อย.', 'กรมสรรพากร'],
    status: 'failed',
    messages: [],
  },
];

export const dashboardStats: DashboardStats = {
  totalQuestions: 48290,
  todayQuestions: 156,
  avgResponseTime: '2.3 วินาที',
  satisfactionRate: 94.5,
};

export const agencyUsageData = [
  { name: 'อย.', value: 12450, fill: 'hsl(145 55% 40%)' },
  { name: 'กรมสรรพากร', value: 18320, fill: 'hsl(213 70% 45%)' },
  { name: 'กรมการปกครอง', value: 9870, fill: 'hsl(25 85% 55%)' },
  { name: 'กรมที่ดิน', value: 7650, fill: 'hsl(280 50% 50%)' },
];

export const weeklyTrendData = [
  { day: 'จันทร์', questions: 180 },
  { day: 'อังคาร', questions: 210 },
  { day: 'พุธ', questions: 195 },
  { day: 'พฤหัสบดี', questions: 240 },
  { day: 'ศุกร์', questions: 220 },
  { day: 'เสาร์', questions: 90 },
  { day: 'อาทิตย์', questions: 65 },
];

export const categoryData = [
  { category: 'สอบถามข้อมูล', count: 22450 },
  { category: 'ตรวจสอบสถานะ', count: 12300 },
  { category: 'ขั้นตอนดำเนินการ', count: 8900 },
  { category: 'กฎหมาย/ระเบียบ', count: 4640 },
];
