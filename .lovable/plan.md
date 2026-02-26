

# Clean Code, Refactor และสร้าง Mockup APIs

## ภาพรวม

Refactor โปรเจคให้แบ่งโครงสร้างชัดเจนระหว่าง Frontend และ Backend โดยสร้าง Supabase Edge Functions เป็น Mockup APIs สำหรับ 4 หน่วยงาน พร้อม Frontend service layer เรียกใช้งาน

---

## 1. Refactor Frontend - แยกโครงสร้างไฟล์ให้ชัดเจน

### 1.1 แยก Types ออกจาก Mock Data
- สร้าง `src/types/agency.ts` - Agency, AgentStep types
- สร้าง `src/types/chat.ts` - ChatMessage, ConversationHistory types
- สร้าง `src/types/dashboard.ts` - DashboardStats types
- สร้าง `src/types/index.ts` - re-export ทั้งหมด

### 1.2 สร้าง API Service Layer
- สร้าง `src/services/agencyApi.ts` - ฟังก์ชันเรียก Edge Functions ของแต่ละหน่วยงาน
- สร้าง `src/services/chatApi.ts` - ฟังก์ชันส่งคำถามและรับคำตอบ
- สร้าง `src/services/dashboardApi.ts` - ฟังก์ชันดึงสถิติ

### 1.3 สร้าง Custom Hooks
- สร้าง `src/hooks/useChat.ts` - แยก chat logic (messages, send, rate, typing, steps) ออกจาก ChatPage และ PublicPortal ให้ใช้ร่วมกัน
- สร้าง `src/hooks/useAgencies.ts` - React Query hook ดึงข้อมูลหน่วยงาน
- สร้าง `src/hooks/useDashboard.ts` - React Query hook ดึงสถิติ

### 1.4 Refactor Pages
- `ChatPage.tsx` - ใช้ `useChat` hook แทน logic ที่ซ้ำกัน
- `PublicPortal.tsx` - ใช้ `useChat` hook เช่นกัน ลด code ซ้ำ
- แยก Landing section ของ PublicPortal เป็น `src/components/public/LandingHero.tsx`, `src/components/public/AgencyCards.tsx`, `src/components/public/SuggestedQuestions.tsx`

---

## 2. Backend - สร้าง Mockup APIs (Supabase Edge Functions)

สร้าง Edge Functions 5 ตัว deploy บน Lovable Cloud:

### 2.1 `agency-fda` - API จำลองสำนักงาน อย.
- `POST /agency-fda` รับ `{ query: string }`
- ตอบข้อมูลจำลองเกี่ยวกับทะเบียนยา อาหาร เครื่องสำอาง
- มี delay จำลอง 500ms

### 2.2 `agency-revenue` - API จำลองกรมสรรพากร
- `POST /agency-revenue` รับ `{ query: string }`
- ตอบข้อมูลจำลองเกี่ยวกับภาษี การยื่นแบบ สิทธิลดหย่อน

### 2.3 `agency-dopa` - API จำลองกรมการปกครอง
- `POST /agency-dopa` รับ `{ query: string }`
- ตอบข้อมูลจำลองเกี่ยวกับทะเบียนราษฎร์ บัตรประชาชน

### 2.4 `agency-land` - API จำลองกรมที่ดิน
- `POST /agency-land` รับ `{ query: string }`
- ตอบข้อมูลจำลองเกี่ยวกับโฉนดที่ดิน ราคาประเมิน

### 2.5 `ai-chat` - API Orchestrator หลัก
- `POST /ai-chat` รับ `{ query: string }`
- วิเคราะห์คำถาม เลือกหน่วยงานที่เกี่ยวข้อง
- เรียก agency functions ที่เกี่ยวข้อง
- รวบรวมคำตอบและส่งกลับพร้อมแหล่งอ้างอิง
- ใช้ Lovable AI เพื่อสังเคราะห์คำตอบ

### รูปแบบ Response มาตรฐาน
```text
{
  "success": true,
  "agency": "fda",
  "data": {
    "answer": "...",
    "references": [...],
    "confidence": 0.95
  },
  "responseTime": 520
}
```

---

## 3. เชื่อม Frontend กับ Backend

### 3.1 ปรับ `useChat` hook
- เรียก `ai-chat` Edge Function แทนการใช้ mock data โดยตรง
- แสดง agent steps แบบ real-time ตาม response ที่ได้
- Fallback กลับไปใช้ mock data ถ้า API ไม่พร้อม

### 3.2 ปรับ Supabase Client
- สร้าง `src/integrations/supabase/client.ts` (ถ้ายังไม่มี) สำหรับเรียก Edge Functions

---

## รายละเอียดทางเทคนิค

### ไฟล์ใหม่ที่สร้าง
- `src/types/agency.ts`
- `src/types/chat.ts`
- `src/types/dashboard.ts`
- `src/types/index.ts`
- `src/services/agencyApi.ts`
- `src/services/chatApi.ts`
- `src/services/dashboardApi.ts`
- `src/hooks/useChat.ts`
- `src/hooks/useAgencies.ts`
- `src/hooks/useDashboard.ts`
- `src/components/public/LandingHero.tsx`
- `src/components/public/AgencyCards.tsx`
- `src/components/public/SuggestedQuestions.tsx`
- `supabase/functions/agency-fda/index.ts`
- `supabase/functions/agency-revenue/index.ts`
- `supabase/functions/agency-dopa/index.ts`
- `supabase/functions/agency-land/index.ts`
- `supabase/functions/ai-chat/index.ts`

### ไฟล์ที่แก้ไข
- `src/data/mockData.ts` - ลบ types (ย้ายไป `src/types`), เก็บเฉพาะ mock data เป็น fallback
- `src/pages/ChatPage.tsx` - ใช้ `useChat` hook
- `src/pages/PublicPortal.tsx` - ใช้ `useChat` hook + แยก components
- `src/pages/DashboardPage.tsx` - ใช้ `useDashboard` hook
- `src/pages/AgenciesPage.tsx` - ใช้ `useAgencies` hook
- `supabase/config.toml` - เพิ่ม function configs

### ลำดับการพัฒนา
1. เชื่อมต่อ Supabase กับโปรเจค
2. สร้าง types แยกไฟล์
3. สร้าง Edge Functions ทั้ง 5 ตัว
4. สร้าง service layer และ hooks
5. Refactor pages ให้ใช้ hooks ใหม่
6. แยก components ของ PublicPortal

