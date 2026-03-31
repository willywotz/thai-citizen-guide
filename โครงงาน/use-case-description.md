# Use Case Description — AI Chatbot Portal

---

## UC-01: ดูหน้าหลักและข้อมูลหน่วยงาน

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-01 |
| **Use Case Name** | ดูหน้าหลักและข้อมูลหน่วยงาน |
| **Actor** | ประชาชน (Citizen) |
| **Precondition** | ผู้ใช้เปิดเว็บเบราว์เซอร์และเข้าถึง URL ของระบบ |
| **Postcondition** | ผู้ใช้เห็นข้อมูลหน่วยงานภาครัฐที่ระบบรองรับและคำถามตัวอย่าง |

**Main Flow:**
1. ผู้ใช้เข้าสู่ URL ของ Public Portal
2. ระบบแสดง Landing Page ประกอบด้วย Hero Section และช่องพิมพ์คำถาม
3. ระบบดึงรายการหน่วยงานที่ active จาก API (`GET /api/v1/agencies`) แสดงเป็น Agency Cards
4. แต่ละ Card แสดง: ชื่อหน่วยงาน, Icon, คำอธิบาย และคำถามตัวอย่าง
5. ผู้ใช้สามารถคลิกคำถามตัวอย่างเพื่อเริ่มสนทนาทันที

**Alternative Flow:**
- A1: หาก API ไม่ตอบสนอง ระบบแสดงข้อมูลหน่วยงานจาก Fallback Data แทน

---

## UC-02: สอบถามข้อมูลผ่าน Chatbot

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-02 |
| **Use Case Name** | สอบถามข้อมูลผ่าน Chatbot |
| **Actor** | ประชาชน (Citizen) |
| **Precondition** | ผู้ใช้อยู่ที่หน้า Public Portal |
| **Postcondition** | ผู้ใช้ได้รับคำตอบที่สังเคราะห์จาก AI พร้อม Agent Steps และ References |
| **Include** | UC-17, UC-18, UC-19, UC-20, UC-21 |
| **Extend** | UC-16 |

**Main Flow:**
1. ผู้ใช้พิมพ์คำถามภาษาไทยในช่อง Input แล้วกดส่ง
2. ระบบแสดงสถานะ Loading พร้อม Agent Steps แบบ Real-time
3. ระบบเรียก UC-17 (ตรวจจับหน่วยงาน) → UC-18 (Route) → UC-19 (Query) → UC-20 (สังเคราะห์)
4. ระบบแสดงคำตอบในรูปแบบ Markdown พร้อม Badge หน่วยงานที่เกี่ยวข้อง
5. ระบบแสดง References ลิงก์ไปยังเว็บไซต์หน่วยงาน
6. UC-21 บันทึก Conversation และ Message ลงฐานข้อมูล

**Alternative Flow:**
- A1: หากไม่พบ Keyword ที่ตรงกับหน่วยงานใด ระบบ Fallback ไปยัง อย. เป็นค่าเริ่มต้น
- A2: หาก LLM ไม่ตอบสนองภายในเวลาที่กำหนด ระบบแสดงข้อความ Error และแนะนำให้ลองใหม่

---

## UC-03: ดูคำตอบที่สังเคราะห์

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-03 |
| **Use Case Name** | ดูคำตอบที่สังเคราะห์ |
| **Actor** | ประชาชน (Citizen) |
| **Precondition** | UC-02 หรือ UC-11 ทำงานเสร็จสมบูรณ์แล้ว |
| **Postcondition** | ผู้ใช้อ่านคำตอบที่ประกอบด้วยข้อมูลจากหลายหน่วยงาน |

**Main Flow:**
1. ระบบแสดงข้อความ AI ฝั่งซ้ายของหน้าจอในรูปแบบ Markdown
2. แสดง Badge ชื่อหน่วยงานที่ใช้ตอบใต้ข้อความ
3. แสดง Agent Steps Timeline แสดงขั้นตอนที่ระบบดำเนินการ (เวลาที่ใช้แต่ละขั้น)
4. แสดงคะแนน Confidence ของคำตอบ

---

## UC-04: ดูแหล่งอ้างอิง

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-04 |
| **Use Case Name** | ดูแหล่งอ้างอิง |
| **Actor** | ประชาชน (Citizen) |
| **Precondition** | UC-03 แสดงคำตอบเรียบร้อยแล้ว |
| **Postcondition** | ผู้ใช้คลิก Link ไปยังเว็บไซต์หน่วยงานต้นทางได้ |

**Main Flow:**
1. ระบบแสดงส่วน References ใต้คำตอบ
2. แต่ละ Reference แสดงชื่อเอกสาร/หน้าเว็บและ URL ของหน่วยงาน
3. ผู้ใช้คลิก Link เพื่อเปิดเว็บไซต์หน่วยงานในแท็บใหม่

**Alternative Flow:**
- A1: หาก API ของหน่วยงานไม่ส่ง References กลับมา ระบบไม่แสดงส่วนนี้

---

## UC-05: เข้าสู่ระบบ (Login)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-05 |
| **Use Case Name** | เข้าสู่ระบบ (Login) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่มี Account ในระบบและยังไม่ได้เข้าสู่ระบบ |
| **Postcondition** | เจ้าหน้าที่ได้รับ JWT Token และถูก Redirect ไปยัง Dashboard |

**Main Flow:**
1. เจ้าหน้าที่เปิดหน้า Login (`/login`)
2. กรอก Email และ Password
3. กดปุ่ม "เข้าสู่ระบบ"
4. ระบบส่ง `POST /api/v1/auth/login` พร้อม Credentials
5. Backend ตรวจสอบ Email ในฐานข้อมูลและ Verify Password ด้วย bcrypt
6. หากถูกต้อง ระบบออก JWT Token (อายุ 7 วัน) ส่งกลับ
7. Frontend เก็บ Token และ Redirect ไปหน้า Dashboard

**Alternative Flow:**
- A1: Email หรือ Password ไม่ถูกต้อง → แสดง Error "Invalid credentials"
- A2: Account ถูก Deactivate → แสดง Error "Account is inactive"

---

## UC-06: สมัครสมาชิก (Signup)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-06 |
| **Use Case Name** | สมัครสมาชิก (Signup) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่ยังไม่มี Account ในระบบ |
| **Postcondition** | สร้าง Account ใหม่สำเร็จ พร้อม Redirect ไปหน้า Login |

**Main Flow:**
1. เจ้าหน้าที่เปิดหน้า Signup (`/signup`)
2. กรอก Display Name, Email, Password และ Confirm Password
3. กดปุ่ม "สมัครสมาชิก"
4. ระบบ Validate ข้อมูล (Email format, Password length, ความตรงกันของ Password)
5. ส่ง `POST /api/v1/auth/signup`
6. Backend Hash รหัสผ่านด้วย bcrypt และบันทึก User ลงฐานข้อมูล
7. Redirect ไปหน้า Login

**Alternative Flow:**
- A1: Email ซ้ำกับที่มีอยู่แล้ว → แสดง Error "Email already exists"
- A2: Password ไม่ตรงกัน → แสดง Error ที่ Field Confirm Password

---

## UC-07: รีเซ็ตรหัสผ่าน

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-07 |
| **Use Case Name** | รีเซ็ตรหัสผ่าน |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่มี Account แต่ลืมรหัสผ่าน |
| **Postcondition** | รหัสผ่านถูกเปลี่ยนเรียบร้อย เจ้าหน้าที่สามารถ Login ด้วยรหัสผ่านใหม่ได้ |

**Main Flow:**
1. เจ้าหน้าที่คลิก "ลืมรหัสผ่าน" ที่หน้า Login
2. กรอก Email ที่ลงทะเบียนไว้
3. ระบบส่ง `POST /api/v1/auth/reset-password` สร้าง Reset Token
4. Backend บันทึก `reset_token` และ `reset_token_expires` ลงฐานข้อมูล
5. เจ้าหน้าที่ได้รับ Token และกรอก Password ใหม่
6. ระบบ Verify Token และอัปเดตรหัสผ่าน

**Alternative Flow:**
- A1: Email ไม่มีในระบบ → แสดง Error "Email not found"
- A2: Token หมดอายุ → แสดง Error และให้ขอ Token ใหม่

---

## UC-08: ดู Dashboard และ Analytics

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-08 |
| **Use Case Name** | ดู Dashboard และ Analytics |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว |
| **Postcondition** | เจ้าหน้าที่เห็นข้อมูลสถิติการใช้งานระบบ |

**Main Flow:**
1. เจ้าหน้าที่คลิกเมนู "Dashboard" บน Sidebar
2. ระบบเรียก `GET /api/v1/dashboard/stats` พร้อม JWT Token
3. ระบบแสดง Summary Cards: Total Queries, Active Agencies, Avg Response Time, Feedback Score
4. แสดง Line Chart จำนวน Query ต่อวัน (Recharts)
5. แสดง Bar Chart จำนวนการใช้งานแต่ละหน่วยงาน
6. แสดง Pie Chart สัดส่วน Rating (👍/👎)

**Alternative Flow:**
- A1: ยังไม่มีข้อมูลในระบบ → แสดง Empty State พร้อมคำแนะนำ

---

## UC-09: จัดการหน่วยงาน (CRUD)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-09 |
| **Use Case Name** | จัดการหน่วยงาน (CRUD) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว |
| **Postcondition** | ข้อมูลหน่วยงานถูกอัปเดตในฐานข้อมูล |
| **Include** | UC-10 |

**Main Flow (Create):**
1. เจ้าหน้าที่คลิกปุ่ม "เพิ่มหน่วยงาน"
2. กรอกข้อมูล: ชื่อ, ชื่อย่อ, Icon, คำอธิบาย, Connection Type (API/MCP/A2A), Endpoint URL, Auth Method, Data Scope, Response Schema
3. กดปุ่ม "บันทึก"
4. ระบบส่ง `POST /api/v1/agencies` และแสดงหน่วยงานในตาราง

**Main Flow (Update):**
1. เจ้าหน้าที่คลิกปุ่ม Edit บนแถวของหน่วยงาน
2. แก้ไขข้อมูลที่ต้องการ
3. กดปุ่ม "บันทึก" → ระบบส่ง `PUT /api/v1/agencies/{id}`

**Main Flow (Delete):**
1. เจ้าหน้าที่คลิกปุ่ม Delete → ยืนยัน Dialog
2. ระบบส่ง `DELETE /api/v1/agencies/{id}`

**Alternative Flow:**
- A1: Endpoint URL รูปแบบไม่ถูกต้อง → แสดง Validation Error

---

## UC-10: ทดสอบการเชื่อมต่อหน่วยงาน

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-10 |
| **Use Case Name** | ทดสอบการเชื่อมต่อหน่วยงาน |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่อยู่ที่หน้าแก้ไขหน่วยงาน และกรอก Endpoint URL แล้ว |
| **Postcondition** | ระบบแสดงผลการทดสอบว่าเชื่อมต่อสำเร็จหรือล้มเหลว |

**Main Flow:**
1. เจ้าหน้าที่คลิกปุ่ม "Test Connection"
2. ระบบส่ง `POST /api/v1/agencies/{id}/test`
3. Backend ส่ง HTTP Request ไปยัง Endpoint ของหน่วยงาน
4. หากได้รับ Response ภายใน Timeout → แสดง "เชื่อมต่อสำเร็จ" (สีเขียว) พร้อม Response Time
5. บันทึกผลลงตาราง ConnectionLog

**Alternative Flow:**
- A1: Connection Timeout → แสดง "เชื่อมต่อล้มเหลว" (สีแดง) พร้อมรายละเอียด Error

---

## UC-11: สนทนากับ AI (Admin Chat)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-11 |
| **Use Case Name** | สนทนากับ AI (Admin Chat) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว |
| **Postcondition** | เจ้าหน้าที่ได้รับคำตอบพร้อม Agent Steps และ References |
| **Include** | UC-17, UC-18, UC-19, UC-20, UC-21 |
| **Extend** | UC-16 |

**Main Flow:**
1. เจ้าหน้าที่คลิกเมนู "Chat" บน Sidebar
2. พิมพ์คำถามภาษาไทยในช่อง Input
3. ระบบประมวลผลผ่าน Multi-Agent Pipeline เช่นเดียวกับ UC-02
4. แสดงคำตอบพร้อม Agent Steps Timeline ฝั่งขวาหรือใต้ข้อความ
5. แสดง Sources และปุ่ม Feedback (👍/👎) ใต้ข้อความ AI

---

## UC-12: ดูประวัติการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-12 |
| **Use Case Name** | ดูประวัติการสนทนา |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว และมีประวัติการสนทนาในระบบ |
| **Postcondition** | เจ้าหน้าที่เห็นรายการ Conversation ทั้งหมด |
| **Include** | UC-13 |
| **Extend** | UC-14, UC-15 |

**Main Flow:**
1. เจ้าหน้าที่คลิกเมนู "History" บน Sidebar
2. ระบบเรียก `GET /api/v1/conversations` ดึงรายการ Conversation
3. แสดงรายการเรียงตามเวลาล่าสุดก่อน แต่ละรายการแสดง: Title, Preview, Agencies, Status, จำนวนข้อความ, วันที่

---

## UC-13: ค้นหาประวัติการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-13 |
| **Use Case Name** | ค้นหาประวัติการสนทนา |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่อยู่ที่หน้า History (UC-12) |
| **Postcondition** | รายการ Conversation ถูกกรองตามเงื่อนไขที่ระบุ |

**Main Flow:**
1. เจ้าหน้าที่พิมพ์ Keyword ในช่อง Search หรือเลือก Filter หน่วยงาน
2. ระบบกรองรายการ Conversation แบบ Real-time (Client-side filtering)
3. แสดงเฉพาะรายการที่ตรงกับเงื่อนไข

**Alternative Flow:**
- A1: ไม่พบรายการที่ตรงกัน → แสดง "ไม่พบผลการค้นหา"

---

## UC-14: ลบการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-14 |
| **Use Case Name** | ลบการสนทนา |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่อยู่ที่หน้า History และมี Conversation ที่ต้องการลบ |
| **Postcondition** | Conversation และ Messages ที่เกี่ยวข้องถูกลบออกจากฐานข้อมูล |

**Main Flow:**
1. เจ้าหน้าที่คลิกปุ่ม Delete บน Conversation ที่ต้องการลบ
2. ระบบแสดง Confirmation Dialog "ยืนยันการลบ?"
3. เจ้าหน้าที่ยืนยัน → ระบบส่ง `DELETE /api/v1/conversations/{id}`
4. Backend ลบ Conversation และ Messages ที่เกี่ยวข้อง (CASCADE DELETE)
5. ระบบ Refresh รายการ History

**Alternative Flow:**
- A1: เจ้าหน้าที่กด "ยกเลิก" → ปิด Dialog โดยไม่ลบ

---

## UC-15: Export ประวัติเป็น PDF

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-15 |
| **Use Case Name** | Export ประวัติเป็น PDF |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Precondition** | เจ้าหน้าที่อยู่ที่หน้า History และเลือก Conversation ที่ต้องการ Export |
| **Postcondition** | ไฟล์ PDF ถูกดาวน์โหลดไปยังเครื่องของเจ้าหน้าที่ |

**Main Flow:**
1. เจ้าหน้าที่คลิกปุ่ม Export บน Conversation
2. Frontend ดึงข้อมูล Messages ของ Conversation
3. ใช้ jsPDF Library สร้างไฟล์ PDF ฝั่ง Client
4. PDF ประกอบด้วย: ชื่อการสนทนา, วันที่, หน่วยงานที่เกี่ยวข้อง และบทสนทนาทั้งหมด
5. Browser Download ไฟล์ PDF โดยอัตโนมัติ

---

## UC-16: ส่ง Feedback (Rating)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-16 |
| **Use Case Name** | ส่ง Feedback (Rating) |
| **Actor** | ประชาชน (Citizen) / เจ้าหน้าที่ (Staff) |
| **Precondition** | UC-02 หรือ UC-11 ได้แสดงคำตอบแล้ว |
| **Postcondition** | Rating และ Feedback Text ถูกบันทึกลงฐานข้อมูล ส่งผลต่อ Dashboard Analytics |

**Main Flow:**
1. ผู้ใช้คลิกปุ่ม 👍 หรือ 👎 ใต้ข้อความ AI
2. หากคลิก 👎 ระบบแสดง Dialog ให้กรอก Feedback Text เพิ่มเติม
3. ระบบส่ง `POST /api/v1/feedback` พร้อม `{message_id, rating, feedback_text}`
4. Backend อัปเดตฟิลด์ `rating` และ `feedback_text` ของ Message ในฐานข้อมูล
5. ปุ่ม Rating เปลี่ยนสีเพื่อแสดงว่าได้ให้ Feedback แล้ว

**Alternative Flow:**
- A1: ผู้ใช้ปิด Dialog โดยไม่กรอก Feedback Text → บันทึกเฉพาะ Rating

---

## UC-17: ตรวจจับหน่วยงานจาก Keyword

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-17 |
| **Use Case Name** | ตรวจจับหน่วยงานจาก Keyword |
| **Actor** | ระบบ (Internal) |
| **Precondition** | ได้รับ Query String จากผู้ใช้ |
| **Postcondition** | ได้รายการ Agency ID ที่เกี่ยวข้องกับคำถาม |
| **Include** | UC-18 |

**Main Flow:**
1. ระบบแปลง Query เป็นตัวพิมพ์เล็ก
2. เปรียบเทียบกับ Keyword Dictionary ของแต่ละหน่วยงาน:
   - "ยา", "อาหาร", "เครื่องสำอาง" → fda (อย.)
   - "ภาษี", "สรรพากร", "vat" → revenue (กรมสรรพากร)
   - "บัตรประชาชน", "ทะเบียนบ้าน" → dopa (กรมการปกครอง)
   - "ที่ดิน", "โฉนด", "ราคาประเมิน" → land (กรมที่ดิน)
3. คืนรายการ Agency ID ที่ match ทั้งหมด

**Alternative Flow:**
- A1: ไม่พบ Keyword ที่ตรงกัน → คืน ["fda"] เป็น Default Fallback

---

## UC-18: Route คำถามด้วย LangGraph

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-18 |
| **Use Case Name** | Route คำถามด้วย LangGraph |
| **Actor** | ระบบ (Internal) |
| **Precondition** | ได้รายการ Agency ID จาก UC-17 |
| **Postcondition** | ยืนยันและ/หรือขยายรายการ Agency ที่จะ Query |
| **Include** | UC-19 |

**Main Flow:**
1. ระบบโหลด data_scope และ Config ของแต่ละหน่วยงานจากฐานข้อมูล
2. LangGraph สร้าง Routing Graph จาก Agency Nodes ที่ใช้งานได้
3. LLM ประเมิน Query เทียบกับ data_scope ของแต่ละหน่วยงาน
4. ส่งคืนรายการหน่วยงานที่ควรรับ Query นี้

**Alternative Flow:**
- A1: LangGraph ไม่พร้อมใช้งาน → ใช้ผลจาก UC-17 โดยตรง (Fallback to Keyword Detection)

---

## UC-19: Query หน่วยงานแบบ Parallel

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-19 |
| **Use Case Name** | Query หน่วยงานแบบ Parallel |
| **Actor** | ระบบ (Internal), หน่วยงานภาครัฐ |
| **Precondition** | ได้รายการหน่วยงานที่ต้องการ Query จาก UC-18 |
| **Postcondition** | ได้ข้อมูลคำตอบจากทุกหน่วยงานพร้อมกัน |
| **Include** | UC-20 |

**Main Flow:**
1. ระบบสร้าง Coroutine สำหรับแต่ละหน่วยงาน
2. เรียก `asyncio.gather()` ส่ง Query ไปยังทุกหน่วยงานพร้อมกัน
3. แต่ละ Agency Handler ส่ง HTTP Request ไปยัง Endpoint ของหน่วยงาน
4. รอรับ Response จากทุกหน่วยงาน (หรือ Timeout ที่กำหนด)
5. รวม Response ทั้งหมดพร้อม Metadata (Agent Name, Duration, Status)

**Alternative Flow:**
- A1: หน่วยงานใดหน่วยงานหนึ่ง Timeout → ข้ามหน่วยงานนั้นและใช้ข้อมูลจากหน่วยงานที่เหลือ

---

## UC-20: สังเคราะห์คำตอบด้วย LLM

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-20 |
| **Use Case Name** | สังเคราะห์คำตอบด้วย LLM |
| **Actor** | ระบบ AI (LLM — OpenThai GPT) |
| **Precondition** | ได้รับข้อมูลจากหน่วยงานทั้งหมดจาก UC-19 |
| **Postcondition** | ได้คำตอบเดียวที่ครอบคลุมและเข้าใจง่าย |
| **Include** | UC-21 |

**Main Flow:**
1. ระบบสร้าง Schema-Guide Prompt จาก response_schema ของแต่ละหน่วยงาน
2. รวม Prompt + ข้อมูลจากทุกหน่วยงาน + คำถามต้นฉบับ
3. ส่ง Request ไปยัง LLM Gateway (`thaillm.or.th`) ด้วย HTTP POST
4. LLM สังเคราะห์คำตอบเดียวในภาษาไทย
5. คืนค่า: answer, references, confidence score, agencies ที่ใช้

**Alternative Flow:**
- A1: LLM Gateway ไม่ตอบสนอง → คืน Error Response พร้อมข้อมูลดิบจากหน่วยงาน

---

## UC-21: บันทึกการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-21 |
| **Use Case Name** | บันทึกการสนทนา |
| **Actor** | ระบบ (Internal) |
| **Precondition** | UC-20 สังเคราะห์คำตอบเสร็จแล้ว |
| **Postcondition** | Conversation และ Message ถูกบันทึกลง PostgreSQL |

**Main Flow:**
1. ระบบตรวจสอบว่ามี `conversation_id` ใน Request หรือไม่
2. หากไม่มี → สร้าง Conversation ใหม่พร้อม Title (จากคำถามแรก) และ User
3. สร้าง Message ของผู้ใช้ (role: "user") บันทึกลงฐานข้อมูล
4. สร้าง Message ของ AI (role: "assistant") พร้อม agent_steps, sources, response_time
5. อัปเดต Conversation: message_count, agencies, updated_at

---

## สรุปตาราง Use Cases ทั้งหมด

| UC ID | ชื่อ Use Case | Actor | Include | Extend |
|-------|--------------|-------|---------|--------|
| UC-01 | ดูหน้าหลักและข้อมูลหน่วยงาน | ประชาชน | — | — |
| UC-02 | สอบถามข้อมูลผ่าน Chatbot | ประชาชน | UC-17,18,19,20,21 | UC-16 |
| UC-03 | ดูคำตอบที่สังเคราะห์ | ประชาชน | — | — |
| UC-04 | ดูแหล่งอ้างอิง | ประชาชน | — | — |
| UC-05 | เข้าสู่ระบบ (Login) | เจ้าหน้าที่ | — | — |
| UC-06 | สมัครสมาชิก (Signup) | เจ้าหน้าที่ | — | — |
| UC-07 | รีเซ็ตรหัสผ่าน | เจ้าหน้าที่ | — | — |
| UC-08 | ดู Dashboard และ Analytics | เจ้าหน้าที่ | — | — |
| UC-09 | จัดการหน่วยงาน (CRUD) | เจ้าหน้าที่ | UC-10 | — |
| UC-10 | ทดสอบการเชื่อมต่อหน่วยงาน | เจ้าหน้าที่ | — | — |
| UC-11 | สนทนากับ AI (Admin Chat) | เจ้าหน้าที่ | UC-17,18,19,20,21 | UC-16 |
| UC-12 | ดูประวัติการสนทนา | เจ้าหน้าที่ | UC-13 | UC-14,15 |
| UC-13 | ค้นหาประวัติการสนทนา | เจ้าหน้าที่ | — | — |
| UC-14 | ลบการสนทนา | เจ้าหน้าที่ | — | — |
| UC-15 | Export ประวัติเป็น PDF | เจ้าหน้าที่ | — | — |
| UC-16 | ส่ง Feedback (Rating) | ประชาชน / เจ้าหน้าที่ | — | — |
| UC-17 | ตรวจจับหน่วยงานจาก Keyword | ระบบ | UC-18 | — |
| UC-18 | Route คำถามด้วย LangGraph | ระบบ | UC-19 | — |
| UC-19 | Query หน่วยงานแบบ Parallel | ระบบ / หน่วยงาน | UC-20 | — |
| UC-20 | สังเคราะห์คำตอบด้วย LLM | ระบบ AI | UC-21 | — |
| UC-21 | บันทึกการสนทนา | ระบบ | — | — |
