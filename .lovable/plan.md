

# Phase 2: บันทึกประวัติสนทนาลง Database จริง

## ภาพรวม

ปัจจุบันประวัติสนทนาเป็น mock data ใน Edge Function (`chat-history`) ทั้งหมด ไม่มีการบันทึกจริง ฟีเจอร์นี้จะสร้างตาราง database จริงเพื่อบันทึกทุกการสนทนาและข้อความ แล้วให้ History Page ดึงจาก database แทน

---

## 1. สร้างตาราง Database (Migration)

### 1.1 ตาราง `conversations`
เก็บข้อมูลหลักของแต่ละบทสนทนา

| Column | Type | Description |
|---|---|---|
| id | uuid (PK) | รหัสสนทนา |
| title | text | หัวข้อ (สร้างจากคำถามแรก) |
| preview | text | ข้อความตัวอย่าง (คำถามแรก) |
| agencies | text[] | หน่วยงานที่เกี่ยวข้อง |
| status | text | 'success' หรือ 'failed' |
| message_count | int | จำนวนข้อความ |
| response_time | text | เวลาตอบ |
| created_at | timestamptz | วันที่สร้าง |

### 1.2 ตาราง `messages`
เก็บข้อความแต่ละรายการในบทสนทนา

| Column | Type | Description |
|---|---|---|
| id | uuid (PK) | รหัสข้อความ |
| conversation_id | uuid (FK) | อ้างอิงไป conversations |
| role | text | 'user' หรือ 'assistant' |
| content | text | เนื้อหาข้อความ |
| agent_steps | jsonb | ขั้นตอน agent (nullable) |
| sources | jsonb | แหล่งอ้างอิง (nullable) |
| rating | text | 'up', 'down', หรือ null |
| created_at | timestamptz | เวลาสร้าง |

### 1.3 RLS Policies
- เนื่องจากเป็นระบบ public portal (ไม่มี auth ในตอนนี้) จะตั้ง RLS แบบ public read + insert ก่อน
- เมื่อเพิ่ม authentication ภายหลังจะ restrict ตาม user_id

---

## 2. อัปเดต Edge Function `chat-history`

แก้ไข `supabase/functions/chat-history/index.ts` ให้:
- ดึงข้อมูลจากตาราง `conversations` แทน mock array
- รองรับ search (title/preview) และ filter by agency
- เรียงลำดับตาม `created_at` ล่าสุดก่อน

---

## 3. สร้าง Edge Function `save-conversation`

สร้าง `supabase/functions/save-conversation/index.ts` ที่:
- รับ conversation data (title, preview, agencies, status, messages)
- Insert ลงตาราง `conversations` + `messages`
- ส่งคืน conversation id

---

## 4. อัปเดต Frontend

### 4.1 เพิ่ม service function
- สร้าง `saveConversation()` ใน `src/services/historyApi.ts` เรียก `save-conversation` Edge Function

### 4.2 อัปเดต `useChat` hook
- หลังได้รับคำตอบจาก AI สำเร็จ เรียก `saveConversation()` เพื่อบันทึกลง database
- สร้าง title อัตโนมัติจากคำถามแรก (ตัด 50 ตัวอักษร)

### 4.3 อัปเดต `HistoryPage`
- เพิ่มการแสดง `messageCount` และ `responseTime` ที่ได้จาก database

---

## 5. Seed ข้อมูลเริ่มต้น

Insert mock data 8 รายการที่มีอยู่ใน Edge Function เดิมลงตาราง `conversations` เพื่อให้ History Page ไม่ว่างเปล่าตั้งแต่แรก

---

## สรุปไฟล์ที่ต้องแก้ไข/สร้าง

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| Migration SQL | สร้างตาราง conversations + messages + RLS |
| `supabase/functions/chat-history/index.ts` | ดึงจาก DB แทน mock |
| `supabase/functions/save-conversation/index.ts` | ใหม่ - บันทึกสนทนา |
| `src/services/historyApi.ts` | เพิ่ม saveConversation() |
| `src/hooks/useChat.ts` | เรียก save หลังได้คำตอบ |
| `.lovable/plan.md` | อัปเดต Phase 2 |

