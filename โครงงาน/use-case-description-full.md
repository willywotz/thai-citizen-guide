# Use Case Description — AI Chatbot Portal (Full)

---

## UC-01: ดูหน้าหลักและข้อมูลหน่วยงาน

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-01 |
| **Use Case Name** | ดูหน้าหลักและข้อมูลหน่วยงาน |
| **Actor** | ประชาชน (Citizen) |
| **Description** | ผู้ใช้เปิดเว็บไซต์ระบบ AI Chatbot Portal แล้วเห็นหน้าหลักที่แสดงรายการหน่วยงานภาครัฐที่ระบบรองรับพร้อมคำถามตัวอย่าง |
| **Pre-Condition** | ผู้ใช้มีอินเทอร์เน็ตและสามารถเข้าถึง URL ของระบบได้ |
| **Post-Condition** | ผู้ใช้เห็นรายการหน่วยงานภาครัฐและคำถามตัวอย่าง พร้อมเริ่มสนทนาได้ทันที |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | เปิดเว็บเบราว์เซอร์แล้วพิมพ์ URL ของระบบ เพื่อดูข้อมูลหน่วยงานที่ให้บริการ |
| **System** | โหลด Landing Page และดึงรายการหน่วยงานที่ active จาก API มาแสดงเป็น Agency Cards พร้อมคำถามตัวอย่าง |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | เปิดเบราว์เซอร์และพิมพ์ URL ของระบบ | — |
| 2 | — | แสดง Landing Page พร้อม Hero Section และช่องพิมพ์คำถาม |
| 3 | — | เรียก `GET /api/v1/agencies` เพื่อดึงรายการหน่วยงาน |
| 4 | — | แสดง Agency Cards แต่ละใบมี: ชื่อหน่วยงาน, Icon, คำอธิบาย, คำถามตัวอย่าง |
| 5 | อ่านข้อมูลหน่วยงาน และคลิกคำถามตัวอย่างหรือพิมพ์คำถามเอง | — |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| API ไม่ตอบสนอง | ระบบแสดงข้อมูลหน่วยงานจาก Fallback Data แทน โดยไม่แสดง Error ต่อผู้ใช้ |

---

## UC-02: สอบถามข้อมูลผ่าน Chatbot

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-02 |
| **Use Case Name** | สอบถามข้อมูลผ่าน Chatbot |
| **Actor** | ประชาชน (Citizen) |
| **Description** | ผู้ใช้พิมพ์คำถามภาษาไทยลงในช่อง Input บนหน้า Public Portal ระบบตรวจจับหน่วยงานที่เกี่ยวข้อง ดึงข้อมูลจากหน่วยงานแบบ Parallel และสังเคราะห์คำตอบเดียวด้วย LLM |
| **Pre-Condition** | ผู้ใช้อยู่ที่หน้า Public Portal และระบบ Backend พร้อมใช้งาน |
| **Post-Condition** | ผู้ใช้ได้รับคำตอบที่สังเคราะห์จาก AI พร้อม Agent Steps, Badge หน่วยงาน และ References |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | พิมพ์คำถามภาษาไทยในช่อง Input แล้วกดปุ่มส่ง หรือกด Enter |
| **System** | รับ Query ส่งไปยัง Multi-Agent Pipeline ได้แก่ Keyword Detection → LangGraph Routing → Parallel Query → LLM Synthesis → บันทึกการสนทนา แล้วส่งคำตอบกลับมาแสดงบนหน้าจอ |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | พิมพ์คำถาม เช่น "ยาพาราเซตามอลต้องขึ้นทะเบียน อย. ไหม" แล้วกดส่ง | — |
| 2 | — | ส่ง `POST /api/v1/chat` พร้อม query และ conversation_id |
| 3 | — | แสดงสถานะ Loading พร้อม Agent Steps แบบ Real-time |
| 4 | — | เรียก UC-17: ตรวจจับ Keyword → พบ "ยา", "อย." → จับคู่กับ Agency "fda" |
| 5 | — | เรียก UC-18: LangGraph ยืนยันการ Route ไปยัง Agency "fda" |
| 6 | — | เรียก UC-19: Query Agency "fda" แบบ Parallel ด้วย asyncio.gather() |
| 7 | — | เรียก UC-20: ส่งข้อมูลจาก อย. ไปยัง LLM สังเคราะห์คำตอบ |
| 8 | — | เรียก UC-21: บันทึก Conversation และ Message ลง PostgreSQL |
| 9 | — | แสดงคำตอบในรูปแบบ Markdown พร้อม Badge หน่วยงาน, Agent Steps, References |
| 10 | อ่านคำตอบ และอาจให้ Feedback (UC-16) | — |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ไม่พบ Keyword ที่ตรงกับหน่วยงานใด | Fallback ไปยัง Agency "fda" เป็นค่าเริ่มต้น |
| LLM Gateway ไม่ตอบสนองภายใน Timeout | แสดงข้อความ Error พร้อมข้อมูลดิบจากหน่วยงาน และแนะนำให้ลองใหม่ |

---

## UC-03: ดูคำตอบที่สังเคราะห์

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-03 |
| **Use Case Name** | ดูคำตอบที่สังเคราะห์ |
| **Actor** | ประชาชน (Citizen) |
| **Description** | หลังจากระบบประมวลผล UC-02 เสร็จสิ้น ผู้ใช้ได้อ่านคำตอบที่ผ่านการสังเคราะห์จาก LLM ซึ่งรวมข้อมูลจากหลายหน่วยงานเป็นคำตอบเดียวในภาษาไทย |
| **Pre-Condition** | UC-02 หรือ UC-11 ดำเนินการเสร็จสมบูรณ์และได้รับ Response จาก LLM |
| **Post-Condition** | ผู้ใช้อ่านคำตอบที่ครอบคลุมและเข้าใจง่าย พร้อมเห็นหน่วยงานที่ใช้ตอบ |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | อ่านคำตอบที่แสดงบนหน้าจอ และดู Agent Steps ที่แสดงขั้นตอนการทำงานของระบบ |
| **System** | Render คำตอบ Markdown ฝั่งซ้าย แสดง Badge หน่วยงาน, Agent Steps Timeline พร้อมเวลาที่ใช้แต่ละขั้น และคะแนน Confidence |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | แสดงข้อความ AI ฝั่งซ้ายในรูปแบบ Markdown (หัวข้อ, ตัวหนา, รายการ) |
| 2 | — | แสดง Badge ชื่อหน่วยงานที่ใช้ตอบใต้ข้อความ |
| 3 | — | แสดง Agent Steps Timeline: ชื่อ Step, สถานะ (✅/❌), เวลาที่ใช้ |
| 4 | อ่านคำตอบและ Agent Steps | — |
| 5 | — | แสดงปุ่ม Feedback (👍/👎) ใต้ข้อความ AI |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| LLM คืนคำตอบที่ไม่สมบูรณ์ | แสดงคำตอบที่ได้ร่วมกับข้อความแจ้งว่า "ข้อมูลอาจไม่ครบถ้วน" |

---

## UC-04: ดูแหล่งอ้างอิง

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-04 |
| **Use Case Name** | ดูแหล่งอ้างอิง |
| **Actor** | ประชาชน (Citizen) |
| **Description** | ผู้ใช้ดูรายการ References ที่แสดงใต้คำตอบ และคลิก Link เพื่อเข้าไปยังเว็บไซต์หน่วยงานต้นทาง |
| **Pre-Condition** | UC-03 แสดงคำตอบเรียบร้อยแล้ว และ Agency API ส่ง References กลับมาในผลลัพธ์ |
| **Post-Condition** | ผู้ใช้เข้าถึงแหล่งข้อมูลต้นทางของหน่วยงานภาครัฐผ่าน URL ที่ระบบให้ไว้ |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | อ่านรายการ References ใต้คำตอบ และคลิก Link ที่ต้องการเพื่อดูข้อมูลเพิ่มเติม |
| **System** | แสดงส่วน References ที่ได้จาก Agency Response ประกอบด้วยชื่อเอกสาร/หน้าเว็บและ URL |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | แสดงส่วน "แหล่งอ้างอิง" ใต้คำตอบ AI |
| 2 | — | แสดงรายการ References แต่ละรายการมี: ชื่อเอกสาร และ URL ของหน่วยงาน |
| 3 | คลิก Link ที่ต้องการ | — |
| 4 | — | เปิด URL ในแท็บใหม่ของเบราว์เซอร์ |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Agency API ไม่ส่ง References กลับมา | ระบบซ่อนส่วน References โดยไม่แสดง Error |

---

## UC-05: เข้าสู่ระบบ (Login)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-05 |
| **Use Case Name** | เข้าสู่ระบบ (Login) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่กรอก Email และ Password เพื่อยืนยันตัวตนเข้าสู่ Admin Portal ระบบจะออก JWT Token สำหรับเข้าถึง Endpoints ที่ต้องการ Authentication |
| **Pre-Condition** | เจ้าหน้าที่มี Account ที่ถูกสร้างไว้ในระบบและ Account ยังไม่ถูก Deactivate |
| **Post-Condition** | เจ้าหน้าที่ได้รับ JWT Token และถูก Redirect ไปยังหน้า Dashboard |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | กรอก Email และ Password บนหน้า Login แล้วกดปุ่ม "เข้าสู่ระบบ" |
| **System** | รับ Credentials ตรวจสอบกับฐานข้อมูล Verify Password ด้วย bcrypt ออก JWT Token อายุ 7 วัน และ Redirect ไปยัง Dashboard |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | เปิดหน้า Login (`/login`) | — |
| 2 | — | แสดง Form: ช่อง Email, Password, ปุ่ม "เข้าสู่ระบบ" |
| 3 | กรอก Email และ Password แล้วกดปุ่ม | — |
| 4 | — | Validate รูปแบบ Email และความยาว Password |
| 5 | — | ส่ง `POST /api/v1/auth/login` พร้อม `{email, password}` |
| 6 | — | Backend ค้นหา User ด้วย Email ในฐานข้อมูล |
| 7 | — | Verify Password ด้วย bcrypt.checkpw() |
| 8 | — | ออก JWT Token (HS256, อายุ 10,080 นาที) และส่งกลับ |
| 9 | — | Frontend เก็บ Token ใน Memory และ Redirect ไปหน้า Dashboard |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Email ไม่มีในระบบ | แสดง Error "Invalid credentials" (ไม่เปิดเผยว่า Email ไม่มี เพื่อความปลอดภัย) |
| Password ไม่ถูกต้อง | แสดง Error "Invalid credentials" |
| Account ถูก Deactivate (`is_active = false`) | แสดง Error "Account is inactive" |

---

## UC-06: สมัครสมาชิก (Signup)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-06 |
| **Use Case Name** | สมัครสมาชิก (Signup) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่กรอกข้อมูลส่วนตัวเพื่อสร้าง Account ใหม่ในระบบ ระบบจะ Hash รหัสผ่านด้วย bcrypt ก่อนบันทึก |
| **Pre-Condition** | เจ้าหน้าที่ยังไม่มี Account ในระบบ และ Email ที่ใช้ยังไม่เคยลงทะเบียน |
| **Post-Condition** | สร้าง Account ใหม่ Role "user" ในฐานข้อมูลสำเร็จ และ Redirect ไปหน้า Login |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | กรอก Display Name, Email, Password และ Confirm Password บนหน้า Signup แล้วกดปุ่ม "สมัครสมาชิก" |
| **System** | Validate ข้อมูล Hash รหัสผ่านด้วย bcrypt บันทึก User ลงฐานข้อมูลพร้อม Role "user" และ Redirect ไปหน้า Login |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกลิงก์ "สมัครสมาชิก" จากหน้า Login | — |
| 2 | — | แสดง Form: Display Name, Email, Password, Confirm Password |
| 3 | กรอกข้อมูลครบถ้วนแล้วกดปุ่ม | — |
| 4 | — | Validate: Email format, Password ≥ 8 ตัวอักษร, Password ตรงกับ Confirm Password |
| 5 | — | ส่ง `POST /api/v1/auth/signup` |
| 6 | — | ตรวจสอบว่า Email ซ้ำหรือไม่ใน users table |
| 7 | — | Hash รหัสผ่านด้วย `bcrypt.hashpw()` |
| 8 | — | บันทึก User ลงตาราง users (role: "user", is_active: true) |
| 9 | — | Redirect ไปหน้า Login พร้อมข้อความ "สมัครสมาชิกสำเร็จ" |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Email ซ้ำกับที่มีอยู่แล้ว | แสดง Error "Email already exists" |
| Password ไม่ตรงกับ Confirm Password | แสดง Validation Error ที่ Field Confirm Password ทันที (Client-side) |
| Email รูปแบบไม่ถูกต้อง | แสดง Validation Error ที่ Field Email |

---

## UC-07: รีเซ็ตรหัสผ่าน

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-07 |
| **Use Case Name** | รีเซ็ตรหัสผ่าน |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่ที่ลืมรหัสผ่านสามารถขอ Reset Token และตั้งรหัสผ่านใหม่ได้ผ่านกระบวนการ 2 ขั้นตอน |
| **Pre-Condition** | เจ้าหน้าที่มี Account ในระบบและทราบ Email ที่ลงทะเบียน |
| **Post-Condition** | รหัสผ่านถูกเปลี่ยนเป็นรหัสใหม่ เจ้าหน้าที่สามารถ Login ด้วยรหัสใหม่ได้ |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | กรอก Email เพื่อขอ Reset Token จากนั้นกรอก Token พร้อม Password ใหม่เพื่อเปลี่ยนรหัสผ่าน |
| **System** | สร้าง Reset Token บันทึกลงฐานข้อมูลพร้อมวันหมดอายุ ตรวจสอบ Token และอัปเดตรหัสผ่านใหม่ที่ผ่านการ Hash แล้ว |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิก "ลืมรหัสผ่าน" ที่หน้า Login | — |
| 2 | — | แสดง Form ขอ Email |
| 3 | กรอก Email แล้วกดส่ง | — |
| 4 | — | ส่ง `POST /api/v1/auth/reset-password` พร้อม Email |
| 5 | — | ค้นหา User ด้วย Email สร้าง Reset Token (UUID) บันทึกพร้อม Expiry |
| 6 | รับ Reset Token และกรอก Password ใหม่บนหน้า Reset | — |
| 7 | — | Verify Token ตรงกับ reset_token ในฐานข้อมูลและยังไม่หมดอายุ |
| 8 | — | Hash Password ใหม่และอัปเดตในฐานข้อมูล ลบ Reset Token ออก |
| 9 | — | แสดงข้อความ "เปลี่ยนรหัสผ่านสำเร็จ" และ Redirect ไปหน้า Login |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Email ไม่มีในระบบ | แสดง Error "Email not found" |
| Reset Token หมดอายุ | แสดง Error "Token expired" และแนะนำให้ขอ Token ใหม่ |
| Token ไม่ถูกต้อง | แสดง Error "Invalid token" |

---

## UC-08: ดู Dashboard และ Analytics

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-08 |
| **Use Case Name** | ดู Dashboard และ Analytics |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่ดูสถิติการใช้งานระบบในรูปแบบกราฟและตัวเลขสรุป ประกอบด้วย จำนวนคำถาม การใช้งานหน่วยงาน และสัดส่วน Feedback |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว และมี JWT Token ที่ยังไม่หมดอายุ |
| **Post-Condition** | เจ้าหน้าที่เห็นข้อมูล Analytics ที่เป็นปัจจุบัน |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | คลิกเมนู "Dashboard" บน Sidebar เพื่อดูสถิติการใช้งาน |
| **System** | ดึงข้อมูลสถิติจาก API แสดง Summary Cards, Line Chart, Bar Chart และ Pie Chart ด้วย Recharts Library |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกเมนู "Dashboard" บน Sidebar | — |
| 2 | — | ส่ง `GET /api/v1/dashboard/stats` พร้อม JWT Token ใน Authorization Header |
| 3 | — | Backend คำนวณสถิติจากตาราง conversations, messages, agencies |
| 4 | — | แสดง Summary Cards: Total Queries, Active Agencies, Avg Response Time, Feedback Score |
| 5 | — | Render Line Chart จำนวน Query ต่อวัน (แกน X = วันที่, แกน Y = จำนวน) |
| 6 | — | Render Bar Chart จำนวนการใช้งานแต่ละหน่วยงาน |
| 7 | — | Render Pie Chart สัดส่วน Rating (👍 / 👎) |
| 8 | อ่านข้อมูลสถิติบนหน้าจอ | — |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ยังไม่มีข้อมูลในระบบ | แสดง Empty State พร้อมข้อความ "ยังไม่มีข้อมูล" |
| JWT Token หมดอายุ | Redirect ไปหน้า Login |

---

## UC-09: จัดการหน่วยงาน (CRUD)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-09 |
| **Use Case Name** | จัดการหน่วยงาน (CRUD) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่สามารถเพิ่ม แก้ไข และลบหน่วยงานภาครัฐในระบบ พร้อมกำหนดค่าการเชื่อมต่อ Connection Type, Endpoint URL, Data Scope และ Response Schema |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว |
| **Post-Condition** | ข้อมูลหน่วยงานในฐานข้อมูลถูกอัปเดตตามการกระทำ (Create / Update / Delete) |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | เพิ่ม แก้ไข หรือลบหน่วยงานผ่าน Form บนหน้า Agencies |
| **System** | รับข้อมูล Validate และดำเนินการ Create/Update/Delete กับฐานข้อมูลผ่าน API แล้ว Refresh รายการบนหน้าจอ |

**Flow of Events (Create):**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม "เพิ่มหน่วยงาน" | — |
| 2 | — | แสดง Form: ชื่อ, ชื่อย่อ, Icon, คำอธิบาย, Connection Type, Endpoint URL, Auth Method, Data Scope, Response Schema |
| 3 | กรอกข้อมูลครบถ้วนแล้วกดปุ่ม "บันทึก" | — |
| 4 | — | Validate ข้อมูล (Required Fields, URL Format) |
| 5 | — | ส่ง `POST /api/v1/agencies` พร้อมข้อมูลหน่วยงาน |
| 6 | — | บันทึกข้อมูลลงตาราง agencies และ Refresh รายการ |

**Flow of Events (Update):**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม Edit บนแถวหน่วยงานที่ต้องการแก้ไข | — |
| 2 | — | โหลดข้อมูลหน่วยงานเข้า Form |
| 3 | แก้ไขข้อมูลแล้วกดปุ่ม "บันทึก" | — |
| 4 | — | ส่ง `PUT /api/v1/agencies/{id}` และ Refresh รายการ |

**Flow of Events (Delete):**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม Delete บนแถวหน่วยงาน | — |
| 2 | — | แสดง Confirmation Dialog "ยืนยันการลบหน่วยงานนี้?" |
| 3 | คลิก "ยืนยัน" | — |
| 4 | — | ส่ง `DELETE /api/v1/agencies/{id}` และ Refresh รายการ |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Endpoint URL รูปแบบไม่ถูกต้อง | แสดง Validation Error ที่ Field นั้น |
| เจ้าหน้าที่คลิก "ยกเลิก" ใน Delete Dialog | ปิด Dialog โดยไม่ดำเนินการใดๆ |

---

## UC-10: ทดสอบการเชื่อมต่อหน่วยงาน

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-10 |
| **Use Case Name** | ทดสอบการเชื่อมต่อหน่วยงาน |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่ทดสอบว่า Endpoint URL ของหน่วยงานสามารถเชื่อมต่อได้จริงหรือไม่ ก่อนที่จะ Activate หน่วยงานในระบบ |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้าแก้ไขหน่วยงาน (Agency Detail) และกรอก Endpoint URL แล้ว |
| **Post-Condition** | ระบบแสดงผลการทดสอบว่าเชื่อมต่อสำเร็จหรือล้มเหลว พร้อม Response Time |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | คลิกปุ่ม "Test Connection" บนหน้าแก้ไขหน่วยงาน |
| **System** | ส่ง HTTP Request ไปยัง Endpoint ของหน่วยงาน บันทึกผลลงตาราง ConnectionLog และแสดงผลลัพธ์ต่อเจ้าหน้าที่ |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม "Test Connection" | — |
| 2 | — | ส่ง `POST /api/v1/agencies/{id}/test` |
| 3 | — | Backend ส่ง HTTP Request ไปยัง endpoint_url ของหน่วยงาน |
| 4 | — | วัด Response Time และตรวจสอบ HTTP Status Code |
| 5 | — | บันทึกผลลงตาราง connection_logs |
| 6 | — | แสดงผล: "เชื่อมต่อสำเร็จ ✅" (สีเขียว) พร้อม Response Time หรือ "เชื่อมต่อล้มเหลว ❌" (สีแดง) พร้อม Error |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Connection Timeout (เกิน Timeout ที่กำหนด) | แสดง "Connection Timeout" พร้อมแนะนำให้ตรวจสอบ URL และ Network |
| HTTP Status 4xx/5xx | แสดง Status Code และ Error Message จาก Response |

---

## UC-11: สนทนากับ AI (Admin Chat)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-11 |
| **Use Case Name** | สนทนากับ AI (Admin Chat) |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่สนทนากับ AI ในลักษณะเดียวกับ Public Portal แต่เห็น Agent Steps Timeline และ Sources แบบละเอียด พร้อมสามารถให้ Feedback ได้ |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว |
| **Post-Condition** | เจ้าหน้าที่ได้รับคำตอบพร้อม Agent Steps แบบ Verbose และ References |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | พิมพ์คำถามในช่อง Chat ของ Admin Portal แล้วกดส่ง |
| **System** | ประมวลผลผ่าน Multi-Agent Pipeline เช่นเดียวกับ UC-02 แต่แสดง Agent Steps แบบ Timeline พร้อม Duration ของแต่ละขั้น |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกเมนู "Chat" บน Sidebar | — |
| 2 | — | แสดงหน้า Chat Interface ของ Admin |
| 3 | พิมพ์คำถามแล้วกดส่ง | — |
| 4 | — | ส่ง `POST /api/v1/chat` พร้อม JWT Token |
| 5 | — | ประมวลผล UC-17 → UC-18 → UC-19 → UC-20 → UC-21 |
| 6 | — | แสดงคำตอบ Markdown ฝั่งซ้าย |
| 7 | — | แสดง Agent Steps Timeline: Step Name, Status (✅/⏳/❌), Duration |
| 8 | — | แสดง Sources/References และปุ่ม Feedback (👍/👎) |
| 9 | อ่านคำตอบ และอาจให้ Feedback (UC-16) | — |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| JWT Token หมดอายุระหว่างสนทนา | แสดงข้อความ "Session หมดอายุ" และ Redirect ไปหน้า Login |

---

## UC-12: ดูประวัติการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-12 |
| **Use Case Name** | ดูประวัติการสนทนา |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่ดูรายการ Conversation ทั้งหมดของตนเอง เรียงตามเวลาล่าสุดก่อน พร้อมข้อมูล Preview, หน่วยงาน, Status และจำนวนข้อความ |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว และมีประวัติการสนทนาในฐานข้อมูล |
| **Post-Condition** | เจ้าหน้าที่เห็นรายการ Conversation ทั้งหมดของตน |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | คลิกเมนู "History" บน Sidebar เพื่อดูประวัติการสนทนา |
| **System** | ดึงรายการ Conversation จาก API เรียงตามเวลาล่าสุด และแสดงข้อมูลสรุปแต่ละ Conversation |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกเมนู "History" บน Sidebar | — |
| 2 | — | ส่ง `GET /api/v1/conversations` พร้อม JWT Token |
| 3 | — | Backend ดึง Conversation ของ User คนนั้นเรียงตาม `-created_at` |
| 4 | — | แสดงรายการ: Title, Preview, Agency Badges, Status (success/failed), จำนวนข้อความ, วันที่ |
| 5 | อ่านรายการ Conversation และอาจคลิกดูรายละเอียด | — |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ยังไม่มีประวัติการสนทนา | แสดง Empty State "ยังไม่มีประวัติการสนทนา" |

---

## UC-13: ค้นหาประวัติการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-13 |
| **Use Case Name** | ค้นหาประวัติการสนทนา |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่กรอง Conversation ด้วย Keyword หรือเลือก Filter หน่วยงาน เพื่อค้นหาการสนทนาที่ต้องการ |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้า History (UC-12) และมีรายการ Conversation แสดงอยู่ |
| **Post-Condition** | รายการ Conversation ถูกกรองและแสดงเฉพาะรายการที่ตรงกับเงื่อนไขที่ระบุ |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | พิมพ์ Keyword ในช่อง Search หรือเลือก Filter หน่วยงาน |
| **System** | กรองรายการ Conversation แบบ Real-time (Client-side) โดยเปรียบเทียบกับ Title, Preview และ Agency ของแต่ละ Conversation |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | พิมพ์ Keyword ในช่อง Search | — |
| 2 | — | Filter รายการแบบ Real-time ตาม Title และ Preview ที่มี Keyword นั้น |
| 3 | (ทางเลือก) เลือก Agency ใน Dropdown Filter | — |
| 4 | — | Filter เพิ่มเติมตาม Agency ที่เลือก |
| 5 | — | แสดงเฉพาะรายการที่ตรงกับเงื่อนไขทั้งหมด |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ไม่พบรายการที่ตรงกับเงื่อนไข | แสดง "ไม่พบผลการค้นหา" พร้อมแนะนำให้เปลี่ยน Keyword |

---

## UC-14: ลบการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-14 |
| **Use Case Name** | ลบการสนทนา |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่ลบ Conversation ที่ไม่ต้องการออกจากระบบ โดยระบบจะลบ Messages ที่เกี่ยวข้องทั้งหมดด้วย (CASCADE DELETE) |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้า History และมี Conversation ที่ต้องการลบ |
| **Post-Condition** | Conversation และ Messages ทั้งหมดของ Conversation นั้นถูกลบออกจากฐานข้อมูล |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | คลิกปุ่ม Delete บน Conversation ที่ต้องการลบ และยืนยันการลบ |
| **System** | แสดง Confirmation Dialog ดำเนินการลบผ่าน API และ Refresh รายการ History |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม Delete บน Conversation | — |
| 2 | — | แสดง Confirmation Dialog "ยืนยันการลบการสนทนานี้ใช่หรือไม่?" |
| 3 | คลิกปุ่ม "ยืนยัน" | — |
| 4 | — | ส่ง `DELETE /api/v1/conversations/{id}` พร้อม JWT Token |
| 5 | — | Backend ลบ Messages ทั้งหมด (CASCADE) แล้วลบ Conversation |
| 6 | — | Refresh รายการ History และแสดงข้อความ "ลบสำเร็จ" |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| เจ้าหน้าที่คลิก "ยกเลิก" ใน Dialog | ปิด Dialog โดยไม่ดำเนินการใดๆ รายการ History ไม่เปลี่ยนแปลง |

---

## UC-15: Export ประวัติเป็น PDF

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-15 |
| **Use Case Name** | Export ประวัติเป็น PDF |
| **Actor** | เจ้าหน้าที่ (Staff) |
| **Description** | เจ้าหน้าที่ Export ประวัติการสนทนาที่ต้องการเป็นไฟล์ PDF โดยระบบสร้าง PDF ฝั่ง Client ด้วย jsPDF Library |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้า History และเลือก Conversation ที่ต้องการ Export |
| **Post-Condition** | ไฟล์ PDF ถูกสร้างและดาวน์โหลดไปยังเครื่องของเจ้าหน้าที่โดยอัตโนมัติ |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | คลิกปุ่ม Export (PDF) บน Conversation ที่ต้องการ |
| **System** | ดึงข้อมูล Messages ของ Conversation สร้าง PDF Document ด้วย jsPDF แล้ว Trigger การดาวน์โหลด |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม Export บน Conversation | — |
| 2 | — | ดึงข้อมูล Messages ทั้งหมดของ Conversation จาก API หรือ State |
| 3 | — | สร้าง PDF Document ด้วย jsPDF ประกอบด้วย: ชื่อการสนทนา, วันที่, หน่วยงาน, บทสนทนาทั้งหมด |
| 4 | — | สร้างชื่อไฟล์: `conversation_{id}_{date}.pdf` |
| 5 | — | เรียก `doc.save()` เพื่อ Trigger Browser Download |
| 6 | ได้รับไฟล์ PDF บนเครื่อง | — |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ข้อมูล Conversation ว่างเปล่า (ไม่มี Messages) | แสดง Error "ไม่สามารถ Export ได้ เนื่องจากไม่มีข้อความ" |

---

## UC-16: ส่ง Feedback (Rating)

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-16 |
| **Use Case Name** | ส่ง Feedback (Rating) |
| **Actor** | ประชาชน (Citizen) / เจ้าหน้าที่ (Staff) |
| **Description** | ผู้ใช้ประเมินคุณภาพคำตอบของ AI ด้วยการกดปุ่ม 👍 หรือ 👎 และอาจกรอกเหตุผลเพิ่มเติมในกรณีที่กด 👎 |
| **Pre-Condition** | UC-02 หรือ UC-11 แสดงคำตอบของ AI เรียบร้อยแล้ว |
| **Post-Condition** | Rating และ Feedback Text ถูกบันทึกลงฟิลด์ `rating` และ `feedback_text` ของ Message ในฐานข้อมูล ส่งผลต่อกราฟ Feedback บน Dashboard |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | กดปุ่ม 👍 หรือ 👎 ใต้ข้อความ AI และอาจกรอกเหตุผลเพิ่มเติม |
| **System** | รับ Rating บันทึกลงฐานข้อมูลผ่าน API และอัปเดตสีปุ่มให้แสดงว่าได้ให้ Feedback แล้ว |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | คลิกปุ่ม 👍 หรือ 👎 ใต้ข้อความ AI | — |
| 2 | — | หากคลิก 👎 แสดง Dialog ให้กรอก Feedback Text เพิ่มเติม |
| 3 | (กรณี 👎) กรอกเหตุผล แล้วกดส่ง | — |
| 4 | — | ส่ง `POST /api/v1/feedback` พร้อม `{message_id, rating: "up"/"down", feedback_text}` |
| 5 | — | Backend อัปเดต `rating` และ `feedback_text` ของ Message ในฐานข้อมูล |
| 6 | — | เปลี่ยนสีปุ่ม Rating ให้แสดงว่าได้ให้ Feedback แล้ว (ปุ่มที่กดเปลี่ยนเป็นสีเข้ม) |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ผู้ใช้ปิด Dialog กรอกเหตุผลโดยไม่กรอกข้อความ | บันทึกเฉพาะ `rating: "down"` โดยไม่มี feedback_text |

---

## UC-17: ตรวจจับหน่วยงานจาก Keyword

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-17 |
| **Use Case Name** | ตรวจจับหน่วยงานจาก Keyword |
| **Actor** | ระบบ (Internal Process) |
| **Description** | ระบบวิเคราะห์ Query ของผู้ใช้เพื่อจับคู่กับหน่วยงานภาครัฐที่เกี่ยวข้อง โดยใช้การเปรียบเทียบ Keyword Dictionary ที่กำหนดไว้ |
| **Pre-Condition** | ได้รับ Query String จากผู้ใช้ผ่าน UC-02 หรือ UC-11 |
| **Post-Condition** | ได้รายการ Agency ID (เช่น ["fda", "revenue"]) ที่เกี่ยวข้องกับคำถาม |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | — (กระบวนการภายใน ผู้ใช้ไม่ได้โต้ตอบโดยตรง) |
| **System** | เรียกฟังก์ชัน `detect_agencies(query)` แปลง Query เป็นตัวพิมพ์เล็ก แล้วเปรียบเทียบกับ Keyword Dictionary ของแต่ละหน่วยงาน |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | รับ Query String จาก Request |
| 2 | — | แปลง Query เป็น Lowercase: `query.lower()` |
| 3 | — | ตรวจสอบ Keyword แต่ละหน่วยงาน: อย. (ยา, อาหาร, เครื่องสำอาง, อย., พาราเซตามอล, นำเข้า) |
| 4 | — | ตรวจสอบ Keyword กรมสรรพากร (ภาษี, ลดหย่อน, สรรพากร, vat, ยื่นแบบ, เงินได้) |
| 5 | — | ตรวจสอบ Keyword กรมการปกครอง (บัตรประชาชน, ทะเบียนราษฎร์, ทะเบียนบ้าน, ปกครอง, เปลี่ยนชื่อ, แจ้งเกิด) |
| 6 | — | ตรวจสอบ Keyword กรมที่ดิน (ที่ดิน, โฉนด, ราคาประเมิน, จดทะเบียน, รังวัด, โอนที่ดิน) |
| 7 | — | รวบรวม Agency ID ที่ match ทั้งหมดคืนค่ากลับ |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| ไม่พบ Keyword ที่ตรงกับหน่วยงานใดเลย | คืนค่า `["fda"]` เป็น Default Fallback |

---

## UC-18: Route คำถามด้วย LangGraph

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-18 |
| **Use Case Name** | Route คำถามด้วย LangGraph |
| **Actor** | ระบบ (Internal Process) |
| **Description** | ระบบใช้ LangGraph สร้าง Routing Graph จาก Agency Nodes แล้วให้ LLM ตัดสินใจ Route Query ไปยังหน่วยงานที่เหมาะสมโดยพิจารณาจาก data_scope ของแต่ละหน่วยงาน |
| **Pre-Condition** | ได้รายการ Agency ID เบื้องต้นจาก UC-17 และโหลดข้อมูล Agency Config จากฐานข้อมูลแล้ว |
| **Post-Condition** | ได้รายการ Agency ที่ผ่านการยืนยันและ/หรือขยายเพิ่มจาก LangGraph เพื่อนำไป Query ใน UC-19 |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | — (กระบวนการภายใน) |
| **System** | โหลด data_scope ของหน่วยงานทั้งหมดจาก DB สร้าง LangGraph Routing Graph และให้ LLM ตัดสินใจเลือก Agency ที่เหมาะสมที่สุดสำหรับ Query นี้ |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | ดึง Agency Config ทั้งหมดที่ active จากฐานข้อมูล (data_scope, endpoint_url) |
| 2 | — | สร้าง LangGraph StateGraph ที่มี Node สำหรับแต่ละหน่วยงาน |
| 3 | — | ส่ง Query พร้อม data_scope ของทุกหน่วยงานไปยัง LLM เพื่อให้ตัดสินใจ |
| 4 | — | LLM คืนรายการ Agency ที่ควรรับ Query นี้ |
| 5 | — | ส่งรายการ Agency ต่อไปยัง UC-19 |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| LangGraph / LLM ไม่พร้อมใช้งาน | ใช้ผลจาก UC-17 โดยตรง (Keyword-based Fallback) |

---

## UC-19: Query หน่วยงานแบบ Parallel

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-19 |
| **Use Case Name** | Query หน่วยงานแบบ Parallel |
| **Actor** | ระบบ (Internal Process), หน่วยงานภาครัฐ (External System) |
| **Description** | ระบบส่ง Query ไปยังทุกหน่วยงานที่เกี่ยวข้องพร้อมกัน (Parallel) ด้วย asyncio.gather() เพื่อลดเวลารอคอย แล้วรวบรวม Response ทั้งหมด |
| **Pre-Condition** | ได้รายการ Agency ที่ต้องการ Query จาก UC-18 และ Agency ทุกหน่วยมี Config ครบถ้วน |
| **Post-Condition** | ได้ข้อมูล Response จากทุกหน่วยงาน (หรือที่ตอบได้ภายใน Timeout) พร้อม Metadata |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | — (กระบวนการภายใน) |
| **System** | สร้าง Coroutine สำหรับแต่ละหน่วยงาน ส่งพร้อมกันด้วย asyncio.gather() รอรับ Response แล้วรวบรวมพร้อม Agent Step Metadata ส่งต่อ UC-20 |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | สร้าง Async Coroutine สำหรับแต่ละ Agency ใน Agency List |
| 2 | — | เรียก `await asyncio.gather(*coroutines)` เพื่อรัน Parallel |
| 3 | — | แต่ละ Coroutine ส่ง HTTP Request ไปยัง endpoint_url ของ Agency |
| 4 | — | รอรับ Response จากทุก Agency พร้อมกัน |
| 5 | — | บันทึก Agent Step: Agency Name, Start Time, End Time, Duration, Status |
| 6 | — | รวบรวม Response ทั้งหมดเป็น List พร้อม Metadata |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| หน่วยงานใดหน่วยงานหนึ่ง Timeout | ข้ามหน่วยงานนั้น บันทึก Status "timeout" ใน Agent Step และใช้ข้อมูลจากหน่วยงานที่เหลือ |
| ทุกหน่วยงาน Timeout | คืน Response เปล่า และแสดง Error แก่ผู้ใช้ |

---

## UC-20: สังเคราะห์คำตอบด้วย LLM

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-20 |
| **Use Case Name** | สังเคราะห์คำตอบด้วย LLM |
| **Actor** | ระบบ AI — OpenThai GPT (External System) |
| **Description** | ระบบส่งข้อมูลที่รวบรวมได้จากทุกหน่วยงาน พร้อม Schema-Guide Prompt ไปยัง LLM เพื่อสังเคราะห์เป็นคำตอบเดียวในภาษาไทยที่ครอบคลุมและเข้าใจง่าย |
| **Pre-Condition** | ได้รับข้อมูล Response จากหน่วยงานทั้งหมดจาก UC-19 |
| **Post-Condition** | ได้คำตอบสังเคราะห์พร้อม References และ Confidence Score เพื่อส่งกลับผู้ใช้และบันทึกใน UC-21 |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | — (กระบวนการภายใน) |
| **System** | สร้าง Schema-Guide Prompt จาก response_schema ของแต่ละหน่วยงาน รวม Prompt + ข้อมูลดิบ + Query ส่งไปยัง LLM Gateway และรับคำตอบที่สังเคราะห์แล้ว |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | สร้าง Schema-Guide Prompt จาก response_schema ของหน่วยงานที่ตอบ |
| 2 | — | รวม Prompt Template + ข้อมูลดิบจากหน่วยงาน + Query ต้นฉบับ |
| 3 | — | ส่ง HTTP POST ไปยัง LLM Gateway (thaillm.or.th) พร้อม Prompt |
| 4 | — | LLM (OpenThai GPT) ประมวลผลและสร้างคำตอบภาษาไทย |
| 5 | — | รับ Response จาก LLM: answer (Markdown), references, confidence |
| 6 | — | บันทึก Agent Step: "สังเคราะห์คำตอบ", Duration, Status "completed" |
| 7 | — | ส่งผลลัพธ์ต่อไปยัง UC-21 และ Return กลับ API |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| LLM Gateway ไม่ตอบสนอง (Timeout/Error) | คืน Error Response พร้อมข้อมูลดิบจากหน่วยงานที่ได้ |
| LLM คืนคำตอบที่ว่างเปล่า | แสดงข้อความ "ไม่สามารถสังเคราะห์คำตอบได้" และให้ลองถามใหม่ |

---

## UC-21: บันทึกการสนทนา

| รายการ | รายละเอียด |
|--------|-----------|
| **Use Case ID** | UC-21 |
| **Use Case Name** | บันทึกการสนทนา |
| **Actor** | ระบบ (Internal Process) |
| **Description** | ระบบบันทึก Conversation และ Messages ลงฐานข้อมูล PostgreSQL หลังจากที่ LLM สังเคราะห์คำตอบเสร็จแล้ว เพื่อให้เจ้าหน้าที่สามารถดูประวัติการสนทนาย้อนหลังได้ |
| **Pre-Condition** | UC-20 สังเคราะห์คำตอบสำเร็จและได้รับ Response ครบถ้วน |
| **Post-Condition** | Conversation และ Message (ทั้งของ User และ AI) ถูกบันทึกลงตาราง conversations และ messages ใน PostgreSQL |

**Brief Description:**

| ฝ่าย | คำอธิบาย |
|------|----------|
| **User** | — (กระบวนการภายใน ผู้ใช้ไม่ได้รับรู้โดยตรง) |
| **System** | ตรวจสอบว่ามี Conversation อยู่แล้วหรือไม่ สร้าง Conversation ใหม่ถ้าจำเป็น บันทึก Message ของ User และ AI พร้อม agent_steps, sources และ response_time |

**Flow of Events:**

| ขั้นตอน | User | System |
|---------|------|--------|
| 1 | — | ตรวจสอบ `conversation_id` ใน Request |
| 2 | — | หากไม่มี: สร้าง Conversation ใหม่ (title จาก Query แรก, user_id จาก JWT Token) |
| 3 | — | บันทึก Message ของ User: `{role: "user", content: query, conversation_id}` |
| 4 | — | บันทึก Message ของ AI: `{role: "assistant", content: answer, agent_steps, sources, response_time}` |
| 5 | — | อัปเดต Conversation: `message_count += 2`, `agencies`, `updated_at`, `preview` |
| 6 | — | คืน `conversation_id` กลับใน Response เพื่อให้ Frontend ใช้ในการสนทนาต่อไป |

**Alternative Flow:**

| กรณี | การดำเนินการ |
|------|-------------|
| Database Connection ล้มเหลว | Log Error แต่ยังคืน Response ที่สังเคราะห์ได้ให้ผู้ใช้ (ไม่ Block คำตอบ) |

---

## สรุปตาราง Use Case ทั้งหมด

| UC ID | ชื่อ Use Case | Actor | Pre-Condition | Post-Condition |
|-------|--------------|-------|---------------|----------------|
| UC-01 | ดูหน้าหลักและข้อมูลหน่วยงาน | ประชาชน | เข้าถึง URL ได้ | เห็น Agency Cards |
| UC-02 | สอบถามข้อมูลผ่าน Chatbot | ประชาชน | อยู่ที่หน้า Public Portal | ได้รับคำตอบ + References |
| UC-03 | ดูคำตอบที่สังเคราะห์ | ประชาชน | UC-02 เสร็จสมบูรณ์ | อ่านคำตอบ Markdown ได้ |
| UC-04 | ดูแหล่งอ้างอิง | ประชาชน | UC-03 แสดงคำตอบแล้ว | คลิก Link หน่วยงานได้ |
| UC-05 | เข้าสู่ระบบ (Login) | เจ้าหน้าที่ | มี Account ในระบบ | ได้รับ JWT Token |
| UC-06 | สมัครสมาชิก (Signup) | เจ้าหน้าที่ | ยังไม่มี Account | Account ถูกสร้างสำเร็จ |
| UC-07 | รีเซ็ตรหัสผ่าน | เจ้าหน้าที่ | มี Account แต่ลืม Password | รหัสผ่านใหม่ใช้งานได้ |
| UC-08 | ดู Dashboard และ Analytics | เจ้าหน้าที่ | Login แล้ว | เห็นสถิติการใช้งาน |
| UC-09 | จัดการหน่วยงาน (CRUD) | เจ้าหน้าที่ | Login แล้ว | ข้อมูลหน่วยงานอัปเดต |
| UC-10 | ทดสอบการเชื่อมต่อหน่วยงาน | เจ้าหน้าที่ | กรอก Endpoint URL แล้ว | ทราบสถานะการเชื่อมต่อ |
| UC-11 | สนทนากับ AI (Admin Chat) | เจ้าหน้าที่ | Login แล้ว | ได้รับคำตอบ + Agent Steps |
| UC-12 | ดูประวัติการสนทนา | เจ้าหน้าที่ | Login และมีประวัติ | เห็นรายการ Conversation |
| UC-13 | ค้นหาประวัติการสนทนา | เจ้าหน้าที่ | อยู่ที่หน้า History | รายการถูกกรองตาม Keyword |
| UC-14 | ลบการสนทนา | เจ้าหน้าที่ | อยู่ที่หน้า History | Conversation ถูกลบจาก DB |
| UC-15 | Export ประวัติเป็น PDF | เจ้าหน้าที่ | อยู่ที่หน้า History | ได้ไฟล์ PDF บนเครื่อง |
| UC-16 | ส่ง Feedback (Rating) | ประชาชน / เจ้าหน้าที่ | ได้รับคำตอบ AI แล้ว | Rating บันทึกลง DB |
| UC-17 | ตรวจจับหน่วยงานจาก Keyword | ระบบ | ได้รับ Query String | ได้ Agency ID List |
| UC-18 | Route คำถามด้วย LangGraph | ระบบ | ได้ Agency List เบื้องต้น | ได้ Agency List ที่ยืนยันแล้ว |
| UC-19 | Query หน่วยงานแบบ Parallel | ระบบ / หน่วยงาน | ได้ Agency List จาก UC-18 | ได้ Response จากทุกหน่วยงาน |
| UC-20 | สังเคราะห์คำตอบด้วย LLM | ระบบ AI | ได้ Response จาก UC-19 | ได้คำตอบสังเคราะห์ภาษาไทย |
| UC-21 | บันทึกการสนทนา | ระบบ | UC-20 เสร็จสมบูรณ์ | Conversation + Messages อยู่ใน DB |
