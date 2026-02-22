
# เพิ่ม 5 ฟีเจอร์ใหม่ให้ AI Chatbot Portal กลาง

## ภาพรวมการพัฒนา

เพิ่ม 5 ฟีเจอร์สำคัญ ได้แก่ หน้า System Architecture, Dark Mode, แอนิเมชัน step-by-step แบบ real-time, ระบบ rating, และหน้า Public Portal สำหรับประชาชน

---

## ฟีเจอร์ที่ 1: หน้า System Architecture Diagram

สร้างหน้าใหม่ `src/pages/ArchitecturePage.tsx` แสดง workflow ของ Agentic AI แบบ interactive

- แสดงแผนผังระบบแบบ visual ด้วย React components (กล่อง + เส้นเชื่อม)
- แสดงขั้นตอน: ผู้ใช้ถาม -> AI Agent วิเคราะห์ -> เลือกหน่วยงาน -> สืบค้น -> รวบรวม -> สังเคราะห์คำตอบ
- แต่ละ node สามารถ click เพื่อดูรายละเอียดเพิ่มเติม (expandable)
- แสดงการเชื่อมต่อ 4 หน่วยงาน พร้อมประเภท protocol (MCP/API/A2A)
- เพิ่ม route `/architecture` และเมนูใน Sidebar

## ฟีเจอร์ที่ 2: Dark Mode Toggle

- ติดตั้ง Theme Provider โดยใช้ `next-themes` (มีอยู่แล้วใน dependencies)
- เพิ่มปุ่ม toggle Sun/Moon icon ใน Header ของ `AppLayout.tsx`
- สร้าง `src/components/ThemeProvider.tsx` และ `src/components/ThemeToggle.tsx`
- ครอบ App ด้วย ThemeProvider ใน `App.tsx`
- Dark mode จะใช้ CSS variables ที่มีอยู่แล้วใน `.dark` class ของ `index.css`

## ฟีเจอร์ที่ 3: แอนิเมชัน Step-by-Step แบบ Real-time

ปรับปรุง ChatPage.tsx ให้แสดง agent steps ทีละขั้นตอนแบบ animated

- เมื่อ AI กำลังประมวลผล จะแสดง steps ทีละ step ด้วย `setTimeout` ต่อเนื่อง
- แต่ละ step มีแอนิเมชัน fade-in เมื่อปรากฏ
- Step ที่กำลังทำงาน (active) จะมี spinner/pulse animation
- Step ที่เสร็จแล้ว (done) จะแสดงเครื่องหมายถูกสีเขียว
- Step ที่ยังไม่เริ่ม (pending) จะยังไม่แสดง
- หลังจาก steps ทั้งหมดเสร็จ จึงแสดงคำตอบสุดท้ายพร้อม fade-in
- เพิ่ม keyframes สำหรับ fade-in และ pulse ใน tailwind config

## ฟีเจอร์ที่ 4: ระบบ Rating ความพึงพอใจ

- เพิ่มปุ่ม thumbs up/down ใต้คำตอบของ AI ใน `ChatPage.tsx`
- เมื่อกด rating จะแสดง feedback animation (เช่น สีเปลี่ยน, ข้อความขอบคุณ)
- เก็บ rating ใน state ของ message (เพิ่ม field `rating` ใน `ChatMessage` type)
- แสดงสถานะที่ rated แล้วเพื่อไม่ให้กดซ้ำ

## ฟีเจอร์ที่ 5: หน้า Public Portal สำหรับประชาชน

สร้างหน้า Landing Page สาธารณะ `src/pages/PublicPortal.tsx` แยกจากระบบ admin

- หน้าแรกแบบ public ไม่มี sidebar ไม่มี header admin
- แสดง hero section: ชื่อระบบ, คำอธิบาย, ช่อง input สำหรับถามคำถาม
- แสดงโลโก้ 4 หน่วยงาน พร้อมคำแนะนำบริการที่ให้ได้
- คำถามแนะนำ (suggested questions) แบบ cards
- เมื่อพิมพ์คำถามแล้วส่ง จะ redirect ไปหน้าแชทพร้อมคำถาม
- สร้าง layout แยก `src/components/layout/PublicLayout.tsx` (header เรียบง่าย ไม่มี sidebar)
- เพิ่ม route `/public` ใน App.tsx โดยใช้ PublicLayout

---

## รายละเอียดทางเทคนิค

### ไฟล์ที่สร้างใหม่
- `src/components/ThemeProvider.tsx` - Theme context provider
- `src/components/ThemeToggle.tsx` - Dark/Light toggle button
- `src/pages/ArchitecturePage.tsx` - System architecture diagram
- `src/pages/PublicPortal.tsx` - Public-facing portal page
- `src/components/layout/PublicLayout.tsx` - Layout สำหรับหน้า public

### ไฟล์ที่แก้ไข
- `src/App.tsx` - เพิ่ม ThemeProvider, routes ใหม่
- `src/pages/ChatPage.tsx` - เพิ่ม real-time step animation, rating system
- `src/data/mockData.ts` - เพิ่ม field `rating` ใน ChatMessage type
- `src/components/layout/AppLayout.tsx` - เพิ่ม ThemeToggle ใน header
- `src/components/layout/AppSidebar.tsx` - เพิ่มเมนู Architecture
- `tailwind.config.ts` - เพิ่ม keyframes สำหรับ animations

### ลำดับการพัฒนา
1. Theme Provider + Dark Mode Toggle (ฐานสำหรับทุกหน้า)
2. เพิ่ม animations ใน tailwind config
3. ปรับ ChatPage: real-time steps + rating
4. สร้างหน้า Architecture
5. สร้างหน้า Public Portal + Layout
6. อัปเดต routes ใน App.tsx
