

# แยกหน้า Public Portal ให้มีระบบแชทของตัวเอง

## ปัญหาปัจจุบัน
เมื่อประชาชนพิมพ์คำถามในหน้า Public Portal จะถูก redirect ไปยังหน้า Admin Chat (`/?q=...`) ซึ่งเป็นหน้าเจ้าหน้าที่ ทำให้ประชาชนเห็น sidebar เมนู admin ทั้งหมด

## แนวทางแก้ไข
สร้างระบบแชทแบบ inline ภายในหน้า Public Portal เอง โดยไม่ต้อง redirect ไปหน้า admin

### การทำงานใหม่
1. เมื่อประชาชนพิมพ์คำถามหรือกดคำถามแนะนำ จะสลับจากหน้า landing เป็นหน้าแชทภายใน Public Portal เอง
2. แสดง agent steps แบบ real-time animation เหมือนหน้า admin
3. แสดงคำตอบพร้อมแหล่งอ้างอิงและปุ่ม rating
4. มีปุ่ม "กลับหน้าหลัก" เพื่อกลับไปหน้า landing
5. Header และ Footer ยังคงเป็นของ Public Portal (ไม่มี sidebar admin)

### หน้าตา UI
- **ก่อนถาม**: แสดง landing page เหมือนเดิม (hero, agency cards, suggested questions)
- **หลังถาม**: สลับเป็น chat view เต็มจอ พร้อม header เรียบง่าย, พื้นที่แชท, และช่องพิมพ์ด้านล่าง

---

## รายละเอียดทางเทคนิค

### ไฟล์ที่แก้ไข
- **`src/pages/PublicPortal.tsx`** - เพิ่ม chat state, chat UI, agent step animation, rating system ภายในหน้านี้โดยตรง แทนที่การ `navigate` ไปหน้า admin

### สิ่งที่เปลี่ยน
- ลบ `useNavigate` และการ redirect ไป `/?q=...`
- เพิ่ม state: `messages`, `isTyping`, `activeStepCount`, `chatMode` (boolean สำหรับสลับระหว่าง landing/chat)
- นำ components `AgentStepDisplay` และ `MessageBubble` มาใช้ภายในไฟล์ (หรือ extract เป็น shared component)
- เมื่อ `chatMode = true` แสดง chat UI แทน landing page โดยยังคง header/footer ของ Public Portal
- เพิ่มปุ่ม "ถามคำถามใหม่" หรือ "กลับหน้าหลัก" ใน chat view

