# Use Case Description — AI Chatbot Portal

---

## UC-01: ดูหน้าหลักและข้อมูลหน่วยงาน

| | | |
|---|---|---|
| **Use Case ID** | UC-01 | |
| **Use Case Name** | ดูหน้าหลักและข้อมูลหน่วยงาน | |
| **Actor** | ประชาชน (Citizen) | |
| **Description** | ผู้ใช้เปิดเว็บไซต์ระบบ AI Chatbot Portal แล้วเห็นหน้าหลักที่แสดงรายการหน่วยงานภาครัฐที่ระบบรองรับพร้อมคำถามตัวอย่าง | |
| **Pre-Condition** | ผู้ใช้มีอินเทอร์เน็ตและสามารถเข้าถึง URL ของระบบได้ | |
| **Post-Condition** | ผู้ใช้เห็นรายการหน่วยงานภาครัฐและคำถามตัวอย่าง พร้อมเริ่มสนทนาได้ทันที | |
| **Brief Description** | **User** | **System** |
| | เปิดเว็บเบราว์เซอร์แล้วพิมพ์ URL ของระบบ เพื่อดูข้อมูลหน่วยงานที่ให้บริการ | โหลด Landing Page และดึงรายการหน่วยงานที่ active จาก API มาแสดงเป็น Agency Cards พร้อมคำถามตัวอย่าง |
| **Flow Of Event** | **User** | **System** |
| 1 | เปิดเบราว์เซอร์และพิมพ์ URL ของระบบ | — |
| 2 | — | แสดง Landing Page พร้อม Hero Section และช่องพิมพ์คำถาม |
| 3 | — | เรียก `GET /api/v1/agencies` เพื่อดึงรายการหน่วยงาน |
| 4 | — | แสดง Agency Cards แต่ละใบมี: ชื่อหน่วยงาน, Icon, คำอธิบาย, คำถามตัวอย่าง |
| 5 | อ่านข้อมูลหน่วยงาน และคลิกคำถามตัวอย่างหรือพิมพ์คำถามเอง | — |
| **Alternative** | หาก API ไม่ตอบสนอง → ระบบแสดงข้อมูลหน่วยงานจาก Fallback Data แทน โดยไม่แสดง Error ต่อผู้ใช้ | |

---

## UC-02: สอบถามข้อมูลผ่าน Chatbot

| | | |
|---|---|---|
| **Use Case ID** | UC-02 | |
| **Use Case Name** | สอบถามข้อมูลผ่าน Chatbot | |
| **Actor** | ประชาชน (Citizen) | |
| **Description** | ผู้ใช้พิมพ์คำถามภาษาไทยลงในช่อง Input บนหน้า Public Portal ระบบตรวจจับหน่วยงานที่เกี่ยวข้อง ดึงข้อมูลแบบ Parallel และสังเคราะห์คำตอบด้วย LLM | |
| **Pre-Condition** | ผู้ใช้อยู่ที่หน้า Public Portal และระบบ Backend พร้อมใช้งาน | |
| **Post-Condition** | ผู้ใช้ได้รับคำตอบที่สังเคราะห์จาก AI พร้อม Agent Steps, Badge หน่วยงาน และ References | |
| **Brief Description** | **User** | **System** |
| | พิมพ์คำถามภาษาไทยในช่อง Input แล้วกดปุ่มส่ง หรือกด Enter | รับ Query ส่งไปยัง Multi-Agent Pipeline: Keyword Detection → LangGraph Routing → Parallel Query → LLM Synthesis → บันทึกการสนทนา แล้วส่งคำตอบกลับ |
| **Flow Of Event** | **User** | **System** |
| 1 | พิมพ์คำถาม เช่น "ยาพาราเซตามอลต้องขึ้นทะเบียน อย. ไหม" แล้วกดส่ง | — |
| 2 | — | ส่ง `POST /api/v1/chat` พร้อม query และ conversation_id |
| 3 | — | แสดงสถานะ Loading พร้อม Agent Steps แบบ Real-time |
| 4 | — | เรียก UC-17: ตรวจจับ Keyword → พบ "ยา", "อย." → จับคู่ Agency "fda" |
| 5 | — | เรียก UC-18: LangGraph ยืนยันการ Route ไปยัง Agency "fda" |
| 6 | — | เรียก UC-19: Query Agency "fda" แบบ Parallel ด้วย asyncio.gather() |
| 7 | — | เรียก UC-20: ส่งข้อมูลจาก อย. ไปยัง LLM สังเคราะห์คำตอบ |
| 8 | — | เรียก UC-21: บันทึก Conversation และ Message ลง PostgreSQL |
| 9 | — | แสดงคำตอบ Markdown พร้อม Badge หน่วยงาน, Agent Steps, References |
| 10 | อ่านคำตอบ และอาจให้ Feedback (UC-16) | — |
| **Alternative** | ไม่พบ Keyword ที่ตรงกับหน่วยงานใด → Fallback ไปยัง Agency "fda" เป็นค่าเริ่มต้น | LLM Gateway ไม่ตอบสนองภายใน Timeout → แสดง Error พร้อมข้อมูลดิบจากหน่วยงาน |

---

## UC-03: ดูคำตอบที่สังเคราะห์

| | | |
|---|---|---|
| **Use Case ID** | UC-03 | |
| **Use Case Name** | ดูคำตอบที่สังเคราะห์ | |
| **Actor** | ประชาชน (Citizen) | |
| **Description** | หลังจาก UC-02 เสร็จสิ้น ผู้ใช้ได้อ่านคำตอบที่รวมข้อมูลจากหลายหน่วยงานเป็นคำตอบเดียวในภาษาไทย | |
| **Pre-Condition** | UC-02 หรือ UC-11 ดำเนินการเสร็จสมบูรณ์และได้รับ Response จาก LLM | |
| **Post-Condition** | ผู้ใช้อ่านคำตอบที่ครอบคลุมและเข้าใจง่าย พร้อมเห็นหน่วยงานที่ใช้ตอบ | |
| **Brief Description** | **User** | **System** |
| | อ่านคำตอบที่แสดงบนหน้าจอ และดู Agent Steps ที่แสดงขั้นตอนการทำงาน | Render คำตอบ Markdown ฝั่งซ้าย แสดง Badge หน่วยงาน, Agent Steps Timeline พร้อมเวลาที่ใช้แต่ละขั้น |
| **Flow Of Event** | **User** | **System** |
| 1 | — | แสดงข้อความ AI ฝั่งซ้ายในรูปแบบ Markdown |
| 2 | — | แสดง Badge ชื่อหน่วยงานที่ใช้ตอบใต้ข้อความ |
| 3 | — | แสดง Agent Steps Timeline: ชื่อ Step, สถานะ (✅/❌), เวลาที่ใช้ |
| 4 | อ่านคำตอบและ Agent Steps | — |
| 5 | — | แสดงปุ่ม Feedback (👍/👎) ใต้ข้อความ AI |
| **Alternative** | LLM คืนคำตอบที่ไม่สมบูรณ์ → แสดงคำตอบที่ได้พร้อมข้อความแจ้ง "ข้อมูลอาจไม่ครบถ้วน" | |

---

## UC-04: ดูแหล่งอ้างอิง

| | | |
|---|---|---|
| **Use Case ID** | UC-04 | |
| **Use Case Name** | ดูแหล่งอ้างอิง | |
| **Actor** | ประชาชน (Citizen) | |
| **Description** | ผู้ใช้ดูรายการ References ที่แสดงใต้คำตอบ และคลิก Link เพื่อเข้าถึงเว็บไซต์หน่วยงานต้นทาง | |
| **Pre-Condition** | UC-03 แสดงคำตอบเรียบร้อยแล้ว และ Agency API ส่ง References กลับมาในผลลัพธ์ | |
| **Post-Condition** | ผู้ใช้เข้าถึงแหล่งข้อมูลต้นทางของหน่วยงานภาครัฐผ่าน URL ที่ระบบให้ไว้ | |
| **Brief Description** | **User** | **System** |
| | อ่านรายการ References ใต้คำตอบ และคลิก Link ที่ต้องการเพื่อดูข้อมูลเพิ่มเติม | แสดงส่วน References ที่ได้จาก Agency Response ประกอบด้วยชื่อเอกสารและ URL |
| **Flow Of Event** | **User** | **System** |
| 1 | — | แสดงส่วน "แหล่งอ้างอิง" ใต้คำตอบ AI |
| 2 | — | แสดงรายการ References แต่ละรายการมีชื่อเอกสาร และ URL ของหน่วยงาน |
| 3 | คลิก Link ที่ต้องการ | — |
| 4 | — | เปิด URL ในแท็บใหม่ของเบราว์เซอร์ |
| **Alternative** | Agency API ไม่ส่ง References กลับมา → ระบบซ่อนส่วน References โดยไม่แสดง Error | |

---

## UC-05: เข้าสู่ระบบ (Login)

| | | |
|---|---|---|
| **Use Case ID** | UC-05 | |
| **Use Case Name** | เข้าสู่ระบบ (Login) | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่กรอก Email และ Password เพื่อยืนยันตัวตนเข้าสู่ Admin Portal ระบบออก JWT Token สำหรับเข้าถึง Endpoints ที่ต้องการ Authentication | |
| **Pre-Condition** | เจ้าหน้าที่มี Account ในระบบและยังไม่ได้เข้าสู่ระบบ | |
| **Post-Condition** | เจ้าหน้าที่ได้รับ JWT Token และถูก Redirect ไปยังหน้า Dashboard | |
| **Brief Description** | **User** | **System** |
| | กรอก Email และ Password บนหน้า Login แล้วกดปุ่ม "เข้าสู่ระบบ" | รับ Credentials ตรวจสอบกับฐานข้อมูล Verify Password ด้วย bcrypt ออก JWT Token อายุ 7 วัน และ Redirect ไปยัง Dashboard |
| **Flow Of Event** | **User** | **System** |
| 1 | เปิดหน้า Login (`/login`) | — |
| 2 | — | แสดง Form: ช่อง Email, Password, ปุ่ม "เข้าสู่ระบบ" |
| 3 | กรอก Email และ Password แล้วกดปุ่ม | — |
| 4 | — | Validate รูปแบบ Email และความยาว Password |
| 5 | — | ส่ง `POST /api/v1/auth/login` พร้อม `{email, password}` |
| 6 | — | ค้นหา User ด้วย Email ในฐานข้อมูล |
| 7 | — | Verify Password ด้วย bcrypt.checkpw() |
| 8 | — | ออก JWT Token (HS256, อายุ 10,080 นาที) และส่งกลับ |
| 9 | — | Frontend เก็บ Token และ Redirect ไปหน้า Dashboard |
| **Alternative** | Email/Password ไม่ถูกต้อง → แสดง Error "Invalid credentials" | Account ถูก Deactivate → แสดง Error "Account is inactive" |

---

## UC-06: สมัครสมาชิก (Signup)

| | | |
|---|---|---|
| **Use Case ID** | UC-06 | |
| **Use Case Name** | สมัครสมาชิก (Signup) | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่กรอกข้อมูลส่วนตัวเพื่อสร้าง Account ใหม่ในระบบ ระบบจะ Hash รหัสผ่านด้วย bcrypt ก่อนบันทึก | |
| **Pre-Condition** | เจ้าหน้าที่ยังไม่มี Account และ Email ที่ใช้ยังไม่เคยลงทะเบียน | |
| **Post-Condition** | สร้าง Account ใหม่ Role "user" ในฐานข้อมูลสำเร็จ และ Redirect ไปหน้า Login | |
| **Brief Description** | **User** | **System** |
| | กรอก Display Name, Email, Password และ Confirm Password แล้วกดปุ่ม "สมัครสมาชิก" | Validate ข้อมูล Hash รหัสผ่านด้วย bcrypt บันทึก User พร้อม Role "user" และ Redirect ไปหน้า Login |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกลิงก์ "สมัครสมาชิก" จากหน้า Login | — |
| 2 | — | แสดง Form: Display Name, Email, Password, Confirm Password |
| 3 | กรอกข้อมูลครบถ้วนแล้วกดปุ่ม | — |
| 4 | — | Validate: Email format, Password ≥ 8 ตัวอักษร, Password ตรงกับ Confirm Password |
| 5 | — | ส่ง `POST /api/v1/auth/signup` |
| 6 | — | ตรวจสอบว่า Email ซ้ำหรือไม่ใน users table |
| 7 | — | Hash รหัสผ่านด้วย bcrypt.hashpw() |
| 8 | — | บันทึก User ลงตาราง users (role: "user", is_active: true) |
| 9 | — | Redirect ไปหน้า Login พร้อมข้อความ "สมัครสมาชิกสำเร็จ" |
| **Alternative** | Email ซ้ำกับที่มีอยู่แล้ว → แสดง Error "Email already exists" | Password ไม่ตรงกับ Confirm Password → แสดง Validation Error ที่ Field นั้นทันที |

---

## UC-07: รีเซ็ตรหัสผ่าน

| | | |
|---|---|---|
| **Use Case ID** | UC-07 | |
| **Use Case Name** | รีเซ็ตรหัสผ่าน | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่ที่ลืมรหัสผ่านสามารถขอ Reset Token และตั้งรหัสผ่านใหม่ได้ผ่านกระบวนการ 2 ขั้นตอน | |
| **Pre-Condition** | เจ้าหน้าที่มี Account ในระบบและทราบ Email ที่ลงทะเบียน | |
| **Post-Condition** | รหัสผ่านถูกเปลี่ยนเป็นรหัสใหม่ เจ้าหน้าที่สามารถ Login ด้วยรหัสใหม่ได้ | |
| **Brief Description** | **User** | **System** |
| | กรอก Email เพื่อขอ Reset Token จากนั้นกรอก Token พร้อม Password ใหม่ | สร้าง Reset Token บันทึกลงฐานข้อมูลพร้อมวันหมดอายุ ตรวจสอบ Token และอัปเดตรหัสผ่านที่ Hash แล้ว |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิก "ลืมรหัสผ่าน" ที่หน้า Login | — |
| 2 | — | แสดง Form ขอ Email |
| 3 | กรอก Email แล้วกดส่ง | — |
| 4 | — | ส่ง `POST /api/v1/auth/reset-password` พร้อม Email |
| 5 | — | ค้นหา User ด้วย Email สร้าง Reset Token (UUID) บันทึกพร้อม Expiry |
| 6 | รับ Reset Token และกรอก Password ใหม่บนหน้า Reset | — |
| 7 | — | Verify Token ตรงกับ reset_token ในฐานข้อมูลและยังไม่หมดอายุ |
| 8 | — | Hash Password ใหม่ อัปเดตในฐานข้อมูล และลบ Reset Token ออก |
| 9 | — | แสดงข้อความ "เปลี่ยนรหัสผ่านสำเร็จ" และ Redirect ไปหน้า Login |
| **Alternative** | Email ไม่มีในระบบ → แสดง Error "Email not found" | Reset Token หมดอายุ → แสดง Error "Token expired" และแนะนำให้ขอ Token ใหม่ |

---

## UC-08: ดู Dashboard และ Analytics

| | | |
|---|---|---|
| **Use Case ID** | UC-08 | |
| **Use Case Name** | ดู Dashboard และ Analytics | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่ดูสถิติการใช้งานระบบในรูปแบบกราฟและตัวเลขสรุป ประกอบด้วย จำนวนคำถาม การใช้งานหน่วยงาน และสัดส่วน Feedback | |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว และมี JWT Token ที่ยังไม่หมดอายุ | |
| **Post-Condition** | เจ้าหน้าที่เห็นข้อมูล Analytics ที่เป็นปัจจุบัน | |
| **Brief Description** | **User** | **System** |
| | คลิกเมนู "Dashboard" บน Sidebar เพื่อดูสถิติการใช้งาน | ดึงข้อมูลสถิติจาก API แสดง Summary Cards, Line Chart, Bar Chart และ Pie Chart ด้วย Recharts Library |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกเมนู "Dashboard" บน Sidebar | — |
| 2 | — | ส่ง `GET /api/v1/dashboard/stats` พร้อม JWT Token |
| 3 | — | Backend คำนวณสถิติจากตาราง conversations, messages, agencies |
| 4 | — | แสดง Summary Cards: Total Queries, Active Agencies, Avg Response Time, Feedback Score |
| 5 | — | Render Line Chart จำนวน Query ต่อวัน |
| 6 | — | Render Bar Chart จำนวนการใช้งานแต่ละหน่วยงาน |
| 7 | — | Render Pie Chart สัดส่วน Rating (👍 / 👎) |
| 8 | อ่านข้อมูลสถิติบนหน้าจอ | — |
| **Alternative** | ยังไม่มีข้อมูลในระบบ → แสดง Empty State | JWT Token หมดอายุ → Redirect ไปหน้า Login |

---

## UC-09: จัดการหน่วยงาน (CRUD)

| | | |
|---|---|---|
| **Use Case ID** | UC-09 | |
| **Use Case Name** | จัดการหน่วยงาน (CRUD) | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่สามารถเพิ่ม แก้ไข และลบหน่วยงานภาครัฐในระบบ พร้อมกำหนดค่า Connection Type, Endpoint URL, Data Scope และ Response Schema | |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว | |
| **Post-Condition** | ข้อมูลหน่วยงานในฐานข้อมูลถูกอัปเดตตามการกระทำ (Create / Update / Delete) | |
| **Brief Description** | **User** | **System** |
| | เพิ่ม แก้ไข หรือลบหน่วยงานผ่าน Form บนหน้า Agencies | รับข้อมูล Validate และดำเนินการ Create/Update/Delete กับฐานข้อมูลผ่าน API แล้ว Refresh รายการบนหน้าจอ |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกปุ่ม "เพิ่มหน่วยงาน" | — |
| 2 | — | แสดง Form: ชื่อ, ชื่อย่อ, Icon, คำอธิบาย, Connection Type, Endpoint URL, Data Scope, Response Schema |
| 3 | กรอกข้อมูลครบถ้วนแล้วกดปุ่ม "บันทึก" | — |
| 4 | — | Validate ข้อมูล (Required Fields, URL Format) |
| 5 | — | ส่ง `POST /api/v1/agencies` และบันทึกลงฐานข้อมูล |
| 6 | (Edit) คลิกปุ่ม Edit แก้ไขข้อมูล แล้วกด "บันทึก" | ส่ง `PUT /api/v1/agencies/{id}` และ Refresh รายการ |
| 7 | (Delete) คลิกปุ่ม Delete และยืนยันใน Dialog | ส่ง `DELETE /api/v1/agencies/{id}` และ Refresh รายการ |
| **Alternative** | Endpoint URL รูปแบบไม่ถูกต้อง → แสดง Validation Error | เจ้าหน้าที่คลิก "ยกเลิก" ใน Delete Dialog → ปิด Dialog โดยไม่ดำเนินการ |

---

## UC-10: ทดสอบการเชื่อมต่อหน่วยงาน

| | | |
|---|---|---|
| **Use Case ID** | UC-10 | |
| **Use Case Name** | ทดสอบการเชื่อมต่อหน่วยงาน | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่ทดสอบว่า Endpoint URL ของหน่วยงานสามารถเชื่อมต่อได้จริงหรือไม่ ก่อน Activate หน่วยงานในระบบ | |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้าแก้ไขหน่วยงาน และกรอก Endpoint URL แล้ว | |
| **Post-Condition** | ระบบแสดงผลการทดสอบว่าเชื่อมต่อสำเร็จหรือล้มเหลว พร้อม Response Time | |
| **Brief Description** | **User** | **System** |
| | คลิกปุ่ม "Test Connection" บนหน้าแก้ไขหน่วยงาน | ส่ง HTTP Request ไปยัง Endpoint ของหน่วยงาน บันทึกผลลงตาราง ConnectionLog และแสดงผลลัพธ์ |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกปุ่ม "Test Connection" | — |
| 2 | — | ส่ง `POST /api/v1/agencies/{id}/test` |
| 3 | — | Backend ส่ง HTTP Request ไปยัง endpoint_url ของหน่วยงาน |
| 4 | — | วัด Response Time และตรวจสอบ HTTP Status Code |
| 5 | — | บันทึกผลลงตาราง connection_logs |
| 6 | — | แสดงผล "เชื่อมต่อสำเร็จ ✅" (สีเขียว) พร้อม Response Time หรือ "เชื่อมต่อล้มเหลว ❌" (สีแดง) |
| **Alternative** | Connection Timeout → แสดง "Connection Timeout" และแนะนำให้ตรวจสอบ URL | HTTP 4xx/5xx → แสดง Status Code และ Error Message จาก Response |

---

## UC-11: สนทนากับ AI (Admin Chat)

| | | |
|---|---|---|
| **Use Case ID** | UC-11 | |
| **Use Case Name** | สนทนากับ AI (Admin Chat) | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่สนทนากับ AI ในลักษณะเดียวกับ Public Portal แต่เห็น Agent Steps Timeline แบบละเอียดและสามารถให้ Feedback ได้ | |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว | |
| **Post-Condition** | เจ้าหน้าที่ได้รับคำตอบพร้อม Agent Steps Timeline แบบ Verbose และ References | |
| **Brief Description** | **User** | **System** |
| | พิมพ์คำถามในช่อง Chat ของ Admin Portal แล้วกดส่ง | ประมวลผลผ่าน Multi-Agent Pipeline เช่นเดียวกับ UC-02 แต่แสดง Agent Steps Timeline พร้อม Duration แต่ละขั้น |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกเมนู "Chat" บน Sidebar | — |
| 2 | — | แสดงหน้า Chat Interface ของ Admin |
| 3 | พิมพ์คำถามแล้วกดส่ง | — |
| 4 | — | ส่ง `POST /api/v1/chat` พร้อม JWT Token |
| 5 | — | ประมวลผล UC-17 → UC-18 → UC-19 → UC-20 → UC-21 |
| 6 | — | แสดงคำตอบ Markdown ฝั่งซ้าย |
| 7 | — | แสดง Agent Steps Timeline: Step Name, Status (✅/⏳/❌), Duration |
| 8 | — | แสดง Sources/References และปุ่ม Feedback (👍/👎) |
| 9 | อ่านคำตอบ และอาจให้ Feedback (UC-16) | — |
| **Alternative** | JWT Token หมดอายุระหว่างสนทนา → แสดงข้อความ "Session หมดอายุ" และ Redirect ไปหน้า Login | |

---

## UC-12: ดูประวัติการสนทนา

| | | |
|---|---|---|
| **Use Case ID** | UC-12 | |
| **Use Case Name** | ดูประวัติการสนทนา | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่ดูรายการ Conversation ทั้งหมดของตนเอง เรียงตามเวลาล่าสุดก่อน พร้อมข้อมูล Preview, หน่วยงาน, Status และจำนวนข้อความ | |
| **Pre-Condition** | เจ้าหน้าที่ Login เข้าสู่ระบบแล้ว และมีประวัติการสนทนาในฐานข้อมูล | |
| **Post-Condition** | เจ้าหน้าที่เห็นรายการ Conversation ทั้งหมดของตน | |
| **Brief Description** | **User** | **System** |
| | คลิกเมนู "History" บน Sidebar เพื่อดูประวัติการสนทนา | ดึงรายการ Conversation จาก API เรียงตามเวลาล่าสุด และแสดงข้อมูลสรุปแต่ละ Conversation |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกเมนู "History" บน Sidebar | — |
| 2 | — | ส่ง `GET /api/v1/conversations` พร้อม JWT Token |
| 3 | — | Backend ดึง Conversation ของ User เรียงตาม `-created_at` |
| 4 | — | แสดงรายการ: Title, Preview, Agency Badges, Status, จำนวนข้อความ, วันที่ |
| 5 | อ่านรายการ Conversation | — |
| **Alternative** | ยังไม่มีประวัติการสนทนา → แสดง Empty State "ยังไม่มีประวัติการสนทนา" | |

---

## UC-13: ค้นหาประวัติการสนทนา

| | | |
|---|---|---|
| **Use Case ID** | UC-13 | |
| **Use Case Name** | ค้นหาประวัติการสนทนา | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่กรอง Conversation ด้วย Keyword หรือเลือก Filter หน่วยงาน เพื่อค้นหาการสนทนาที่ต้องการ | |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้า History (UC-12) และมีรายการ Conversation แสดงอยู่ | |
| **Post-Condition** | รายการ Conversation ถูกกรองและแสดงเฉพาะรายการที่ตรงกับเงื่อนไขที่ระบุ | |
| **Brief Description** | **User** | **System** |
| | พิมพ์ Keyword ในช่อง Search หรือเลือก Filter หน่วยงาน | กรองรายการ Conversation แบบ Real-time โดยเปรียบเทียบกับ Title, Preview และ Agency |
| **Flow Of Event** | **User** | **System** |
| 1 | พิมพ์ Keyword ในช่อง Search | — |
| 2 | — | Filter รายการแบบ Real-time ตาม Title และ Preview ที่มี Keyword นั้น |
| 3 | (ทางเลือก) เลือก Agency ใน Dropdown Filter | — |
| 4 | — | Filter เพิ่มเติมตาม Agency ที่เลือก |
| 5 | — | แสดงเฉพาะรายการที่ตรงกับเงื่อนไขทั้งหมด |
| **Alternative** | ไม่พบรายการที่ตรงกัน → แสดง "ไม่พบผลการค้นหา" พร้อมแนะนำให้เปลี่ยน Keyword | |

---

## UC-14: ลบการสนทนา

| | | |
|---|---|---|
| **Use Case ID** | UC-14 | |
| **Use Case Name** | ลบการสนทนา | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่ลบ Conversation ที่ไม่ต้องการออกจากระบบ โดยระบบจะลบ Messages ที่เกี่ยวข้องทั้งหมดด้วย (CASCADE DELETE) | |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้า History และมี Conversation ที่ต้องการลบ | |
| **Post-Condition** | Conversation และ Messages ทั้งหมดของ Conversation นั้นถูกลบออกจากฐานข้อมูล | |
| **Brief Description** | **User** | **System** |
| | คลิกปุ่ม Delete บน Conversation ที่ต้องการลบ และยืนยันการลบ | แสดง Confirmation Dialog ดำเนินการลบผ่าน API (CASCADE DELETE) และ Refresh รายการ History |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกปุ่ม Delete บน Conversation | — |
| 2 | — | แสดง Confirmation Dialog "ยืนยันการลบการสนทนานี้ใช่หรือไม่?" |
| 3 | คลิกปุ่ม "ยืนยัน" | — |
| 4 | — | ส่ง `DELETE /api/v1/conversations/{id}` พร้อม JWT Token |
| 5 | — | Backend ลบ Messages ทั้งหมด (CASCADE) แล้วลบ Conversation |
| 6 | — | Refresh รายการ History และแสดงข้อความ "ลบสำเร็จ" |
| **Alternative** | เจ้าหน้าที่คลิก "ยกเลิก" ใน Dialog → ปิด Dialog โดยไม่ดำเนินการ รายการ History ไม่เปลี่ยนแปลง | |

---

## UC-15: Export ประวัติเป็น PDF

| | | |
|---|---|---|
| **Use Case ID** | UC-15 | |
| **Use Case Name** | Export ประวัติเป็น PDF | |
| **Actor** | เจ้าหน้าที่ (Staff) | |
| **Description** | เจ้าหน้าที่ Export ประวัติการสนทนาเป็นไฟล์ PDF โดยระบบสร้าง PDF ฝั่ง Client ด้วย jsPDF Library | |
| **Pre-Condition** | เจ้าหน้าที่อยู่ที่หน้า History และเลือก Conversation ที่ต้องการ Export | |
| **Post-Condition** | ไฟล์ PDF ถูกสร้างและดาวน์โหลดไปยังเครื่องของเจ้าหน้าที่โดยอัตโนมัติ | |
| **Brief Description** | **User** | **System** |
| | คลิกปุ่ม Export (PDF) บน Conversation ที่ต้องการ | ดึงข้อมูล Messages ของ Conversation สร้าง PDF Document ด้วย jsPDF แล้ว Trigger การดาวน์โหลด |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกปุ่ม Export บน Conversation | — |
| 2 | — | ดึงข้อมูล Messages ทั้งหมดของ Conversation |
| 3 | — | สร้าง PDF ด้วย jsPDF: ชื่อการสนทนา, วันที่, หน่วยงาน, บทสนทนาทั้งหมด |
| 4 | — | ตั้งชื่อไฟล์: `conversation_{id}_{date}.pdf` |
| 5 | — | เรียก `doc.save()` เพื่อ Trigger Browser Download |
| 6 | ได้รับไฟล์ PDF บนเครื่อง | — |
| **Alternative** | Conversation ไม่มี Messages → แสดง Error "ไม่สามารถ Export ได้ เนื่องจากไม่มีข้อความ" | |

---

## UC-16: ส่ง Feedback (Rating)

| | | |
|---|---|---|
| **Use Case ID** | UC-16 | |
| **Use Case Name** | ส่ง Feedback (Rating) | |
| **Actor** | ประชาชน (Citizen) / เจ้าหน้าที่ (Staff) | |
| **Description** | ผู้ใช้ประเมินคุณภาพคำตอบของ AI ด้วยการกดปุ่ม 👍 หรือ 👎 และอาจกรอกเหตุผลเพิ่มเติมในกรณีที่กด 👎 | |
| **Pre-Condition** | UC-02 หรือ UC-11 แสดงคำตอบของ AI เรียบร้อยแล้ว | |
| **Post-Condition** | Rating และ Feedback Text ถูกบันทึกลงฟิลด์ `rating` และ `feedback_text` ของ Message ในฐานข้อมูล | |
| **Brief Description** | **User** | **System** |
| | กดปุ่ม 👍 หรือ 👎 ใต้ข้อความ AI และอาจกรอกเหตุผลเพิ่มเติม | รับ Rating บันทึกลงฐานข้อมูลผ่าน API และอัปเดตสีปุ่มให้แสดงว่าได้ให้ Feedback แล้ว |
| **Flow Of Event** | **User** | **System** |
| 1 | คลิกปุ่ม 👍 หรือ 👎 ใต้ข้อความ AI | — |
| 2 | — | หากคลิก 👎 แสดง Dialog ให้กรอก Feedback Text เพิ่มเติม |
| 3 | (กรณี 👎) กรอกเหตุผล แล้วกดส่ง | — |
| 4 | — | ส่ง `POST /api/v1/feedback` พร้อม `{message_id, rating, feedback_text}` |
| 5 | — | Backend อัปเดต `rating` และ `feedback_text` ของ Message ในฐานข้อมูล |
| 6 | — | เปลี่ยนสีปุ่ม Rating ให้แสดงว่าได้ให้ Feedback แล้ว |
| **Alternative** | ผู้ใช้ปิด Dialog โดยไม่กรอก Feedback Text → บันทึกเฉพาะ `rating: "down"` โดยไม่มี feedback_text | |

---

## UC-17: ตรวจจับหน่วยงานจาก Keyword

| | | |
|---|---|---|
| **Use Case ID** | UC-17 | |
| **Use Case Name** | ตรวจจับหน่วยงานจาก Keyword | |
| **Actor** | ระบบ (Internal Process) | |
| **Description** | ระบบวิเคราะห์ Query ของผู้ใช้เพื่อจับคู่กับหน่วยงานภาครัฐที่เกี่ยวข้อง โดยใช้การเปรียบเทียบ Keyword Dictionary ที่กำหนดไว้ | |
| **Pre-Condition** | ได้รับ Query String จากผู้ใช้ผ่าน UC-02 หรือ UC-11 | |
| **Post-Condition** | ได้รายการ Agency ID ที่เกี่ยวข้องกับคำถาม เช่น ["fda", "revenue"] | |
| **Brief Description** | **User** | **System** |
| | — (กระบวนการภายใน ผู้ใช้ไม่ได้โต้ตอบโดยตรง) | เรียกฟังก์ชัน `detect_agencies(query)` แปลง Query เป็นตัวพิมพ์เล็ก แล้วเปรียบเทียบกับ Keyword Dictionary ของแต่ละหน่วยงาน |
| **Flow Of Event** | **User** | **System** |
| 1 | — | รับ Query String จาก Request |
| 2 | — | แปลง Query เป็น Lowercase: `query.lower()` |
| 3 | — | ตรวจสอบ Keyword อย.: ยา, อาหาร, เครื่องสำอาง, อย., พาราเซตามอล, นำเข้า |
| 4 | — | ตรวจสอบ Keyword กรมสรรพากร: ภาษี, ลดหย่อน, สรรพากร, vat, ยื่นแบบ, เงินได้ |
| 5 | — | ตรวจสอบ Keyword กรมการปกครอง: บัตรประชาชน, ทะเบียนราษฎร์, ทะเบียนบ้าน, แจ้งเกิด |
| 6 | — | ตรวจสอบ Keyword กรมที่ดิน: ที่ดิน, โฉนด, ราคาประเมิน, รังวัด, โอนที่ดิน |
| 7 | — | คืนรายการ Agency ID ที่ match ทั้งหมด |
| **Alternative** | ไม่พบ Keyword ที่ตรงกับหน่วยงานใดเลย → คืนค่า `["fda"]` เป็น Default Fallback | |

---

## UC-18: Route คำถามด้วย LangGraph

| | | |
|---|---|---|
| **Use Case ID** | UC-18 | |
| **Use Case Name** | Route คำถามด้วย LangGraph | |
| **Actor** | ระบบ (Internal Process) | |
| **Description** | ระบบใช้ LangGraph สร้าง Routing Graph จาก Agency Nodes แล้วให้ LLM ตัดสินใจ Route Query ไปยังหน่วยงานที่เหมาะสมโดยพิจารณาจาก data_scope | |
| **Pre-Condition** | ได้รายการ Agency ID เบื้องต้นจาก UC-17 และโหลด Agency Config จากฐานข้อมูลแล้ว | |
| **Post-Condition** | ได้รายการ Agency ที่ผ่านการยืนยันและ/หรือขยายเพิ่มจาก LangGraph เพื่อนำไป Query ใน UC-19 | |
| **Brief Description** | **User** | **System** |
| | — (กระบวนการภายใน) | โหลด data_scope ของหน่วยงานทั้งหมดจาก DB สร้าง LangGraph StateGraph และให้ LLM ตัดสินใจเลือก Agency ที่เหมาะสม |
| **Flow Of Event** | **User** | **System** |
| 1 | — | ดึง Agency Config ทั้งหมดที่ active จากฐานข้อมูล (data_scope, endpoint_url) |
| 2 | — | สร้าง LangGraph StateGraph ที่มี Node สำหรับแต่ละหน่วยงาน |
| 3 | — | ส่ง Query พร้อม data_scope ของทุกหน่วยงานไปยัง LLM |
| 4 | — | LLM คืนรายการ Agency ที่ควรรับ Query นี้ |
| 5 | — | ส่งรายการ Agency ต่อไปยัง UC-19 |
| **Alternative** | LangGraph / LLM ไม่พร้อมใช้งาน → ใช้ผลจาก UC-17 โดยตรง (Keyword-based Fallback) | |

---

## UC-19: Query หน่วยงานแบบ Parallel

| | | |
|---|---|---|
| **Use Case ID** | UC-19 | |
| **Use Case Name** | Query หน่วยงานแบบ Parallel | |
| **Actor** | ระบบ (Internal Process), หน่วยงานภาครัฐ (External System) | |
| **Description** | ระบบส่ง Query ไปยังทุกหน่วยงานที่เกี่ยวข้องพร้อมกัน (Parallel) ด้วย asyncio.gather() เพื่อลดเวลารอคอย แล้วรวบรวม Response ทั้งหมด | |
| **Pre-Condition** | ได้รายการ Agency ที่ต้องการ Query จาก UC-18 และ Agency ทุกหน่วยมี Config ครบถ้วน | |
| **Post-Condition** | ได้ข้อมูล Response จากทุกหน่วยงาน (หรือที่ตอบได้ภายใน Timeout) พร้อม Metadata | |
| **Brief Description** | **User** | **System** |
| | — (กระบวนการภายใน) | สร้าง Coroutine สำหรับแต่ละหน่วยงาน ส่งพร้อมกันด้วย asyncio.gather() รอรับ Response แล้วรวบรวมพร้อม Agent Step Metadata |
| **Flow Of Event** | **User** | **System** |
| 1 | — | สร้าง Async Coroutine สำหรับแต่ละ Agency ใน Agency List |
| 2 | — | เรียก `await asyncio.gather(*coroutines)` เพื่อรัน Parallel |
| 3 | — | แต่ละ Coroutine ส่ง HTTP Request ไปยัง endpoint_url ของ Agency |
| 4 | — | รอรับ Response จากทุก Agency พร้อมกัน |
| 5 | — | บันทึก Agent Step: Agency Name, Start Time, End Time, Duration, Status |
| 6 | — | รวบรวม Response ทั้งหมดเป็น List พร้อม Metadata |
| **Alternative** | หน่วยงานใด Timeout → ข้ามหน่วยงานนั้น บันทึก Status "timeout" และใช้ข้อมูลจากหน่วยงานที่เหลือ | ทุกหน่วยงาน Timeout → คืน Response เปล่า และแสดง Error แก่ผู้ใช้ |

---

## UC-20: สังเคราะห์คำตอบด้วย LLM

| | | |
|---|---|---|
| **Use Case ID** | UC-20 | |
| **Use Case Name** | สังเคราะห์คำตอบด้วย LLM | |
| **Actor** | ระบบ AI — OpenThai GPT (External System) | |
| **Description** | ระบบส่งข้อมูลจากทุกหน่วยงานพร้อม Schema-Guide Prompt ไปยัง LLM เพื่อสังเคราะห์เป็นคำตอบเดียวในภาษาไทย | |
| **Pre-Condition** | ได้รับข้อมูล Response จากหน่วยงานทั้งหมดจาก UC-19 | |
| **Post-Condition** | ได้คำตอบสังเคราะห์พร้อม References และ Confidence Score เพื่อส่งกลับผู้ใช้และบันทึกใน UC-21 | |
| **Brief Description** | **User** | **System** |
| | — (กระบวนการภายใน) | สร้าง Schema-Guide Prompt จาก response_schema ของแต่ละหน่วยงาน รวม Prompt + ข้อมูลดิบ + Query ส่งไปยัง LLM Gateway และรับคำตอบที่สังเคราะห์ |
| **Flow Of Event** | **User** | **System** |
| 1 | — | สร้าง Schema-Guide Prompt จาก response_schema ของหน่วยงานที่ตอบ |
| 2 | — | รวม Prompt Template + ข้อมูลดิบจากหน่วยงาน + Query ต้นฉบับ |
| 3 | — | ส่ง HTTP POST ไปยัง LLM Gateway (thaillm.or.th) |
| 4 | — | LLM (OpenThai GPT) ประมวลผลและสร้างคำตอบภาษาไทย |
| 5 | — | รับ Response: answer (Markdown), references, confidence |
| 6 | — | บันทึก Agent Step: "สังเคราะห์คำตอบ", Duration, Status "completed" |
| 7 | — | ส่งผลลัพธ์ต่อไปยัง UC-21 และ Return กลับ API |
| **Alternative** | LLM Gateway ไม่ตอบสนอง (Timeout/Error) → คืน Error Response พร้อมข้อมูลดิบจากหน่วยงาน | LLM คืนคำตอบว่างเปล่า → แสดงข้อความ "ไม่สามารถสังเคราะห์คำตอบได้" |

---

## UC-21: บันทึกการสนทนา

| | | |
|---|---|---|
| **Use Case ID** | UC-21 | |
| **Use Case Name** | บันทึกการสนทนา | |
| **Actor** | ระบบ (Internal Process) | |
| **Description** | ระบบบันทึก Conversation และ Messages ลงฐานข้อมูล PostgreSQL หลังจาก LLM สังเคราะห์คำตอบเสร็จแล้ว | |
| **Pre-Condition** | UC-20 สังเคราะห์คำตอบสำเร็จและได้รับ Response ครบถ้วน | |
| **Post-Condition** | Conversation และ Message (ทั้งของ User และ AI) ถูกบันทึกลงตาราง conversations และ messages | |
| **Brief Description** | **User** | **System** |
| | — (กระบวนการภายใน ผู้ใช้ไม่ได้รับรู้โดยตรง) | ตรวจสอบว่ามี Conversation อยู่แล้วหรือไม่ สร้าง Conversation ใหม่ถ้าจำเป็น บันทึก Message ของ User และ AI พร้อม agent_steps, sources และ response_time |
| **Flow Of Event** | **User** | **System** |
| 1 | — | ตรวจสอบ `conversation_id` ใน Request |
| 2 | — | หากไม่มี: สร้าง Conversation ใหม่ (title จาก Query แรก, user_id จาก JWT Token) |
| 3 | — | บันทึก Message ของ User: `{role: "user", content: query, conversation_id}` |
| 4 | — | บันทึก Message ของ AI: `{role: "assistant", content: answer, agent_steps, sources, response_time}` |
| 5 | — | อัปเดต Conversation: `message_count += 2`, `agencies`, `updated_at`, `preview` |
| 6 | — | คืน `conversation_id` กลับใน Response สำหรับการสนทนาต่อไป |
| **Alternative** | Database Connection ล้มเหลว → Log Error แต่ยังคืน Response ที่สังเคราะห์ได้ให้ผู้ใช้ (ไม่ Block คำตอบ) | |
