# โครงร่างโครงงาน 5 บท
# การพัฒนาเว็บแอปพลิเคชัน AI Chatbot Portal สำหรับสังเคราะห์คำตอบจากหน่วยงานภาครัฐ
### ระดับปริญญาตรี

---

## บทที่ 1 บทนำ

### 1.1 ความเป็นมาและความสำคัญของปัญหา
- ปัญหาการเข้าถึงข้อมูลบริการภาครัฐของประชาชน
- ข้อมูลกระจายตามหน่วยงานต่าง ๆ ไม่มีจุดรวมศูนย์
- ความต้องการระบบ AI ที่สามารถรวบรวมและสังเคราะห์คำตอบจากหลายหน่วยงานในที่เดียว

### 1.2 วัตถุประสงค์ของโครงงาน
1. เพื่อพัฒนา Web Application สำหรับ AI Chatbot ที่สามารถสังเคราะห์คำตอบจากหลายหน่วยงานภาครัฐ
2. เพื่อพัฒนาระบบจัดการหน่วยงาน (Agency Management) รองรับการเชื่อมต่อหลายรูปแบบ (API, MCP, A2A)
3. เพื่อพัฒนา Dashboard วิเคราะห์สถิติการใช้งานและ Feedback
4. เพื่อพัฒนา Public Portal สำหรับประชาชนทั่วไปในการสอบถามข้อมูล

### 1.3 ขอบเขตของโครงงาน
- ระบบ Public Portal (หน้าสาธารณะสำหรับประชาชน)
- ระบบ Admin Portal (ระบบหลังบ้านสำหรับเจ้าหน้าที่)
- ระบบ Authentication (JWT-based)
- ระบบ Chat ที่ใช้ Multi-Agent Routing (LangGraph)
- ระบบจัดการหน่วยงาน CRUD
- ระบบ Dashboard และ Analytics
- ระบบประวัติการสนทนา

### 1.4 ประโยชน์ที่คาดว่าจะได้รับ
- ประชาชนเข้าถึงข้อมูลภาครัฐได้สะดวกขึ้นผ่านจุดเดียว
- ลดภาระงานของเจ้าหน้าที่ในการตอบคำถามซ้ำ ๆ
- หน่วยงานสามารถวิเคราะห์ความต้องการของประชาชนผ่าน Dashboard

### 1.5 นิยามศัพท์เฉพาะ
- AI Chatbot, LLM, Multi-Agent System, MCP (Model Context Protocol), A2A (Agent-to-Agent), LangGraph, FastAPI, React, JWT

---

## บทที่ 2 ทฤษฎีและงานวิจัยที่เกี่ยวข้อง

### 2.1 แนวคิดและทฤษฎี
- Large Language Model (LLM) และการประยุกต์ใช้
- Multi-Agent System และ Agent Routing
- Model Context Protocol (MCP)
- RESTful API Architecture
- Single Page Application (SPA)

### 2.2 เทคโนโลยีที่เกี่ยวข้อง
- **Frontend**: React, TypeScript, Vite, TailwindCSS, shadcn/ui, React Query
- **Backend**: FastAPI (Python), Tortoise ORM, PostgreSQL
- **AI/ML**: LangChain, LangGraph, OpenAI API
- **Infrastructure**: Docker, Nginx, MCP Server (FastMCP)
- **Authentication**: JWT, Bcrypt

### 2.3 งานวิจัยและโครงงานที่เกี่ยวข้อง
- ระบบ Chatbot ภาครัฐที่มีอยู่ในปัจจุบัน (เช่น ChatGPT, government chatbots)
- งานวิจัยเกี่ยวกับ Multi-Agent LLM Systems
- งานวิจัยเกี่ยวกับ Retrieval-Augmented Generation (RAG)
- เปรียบเทียบข้อดี-ข้อเสียของงานที่เกี่ยวข้อง

---

## บทที่ 3 วิธีดำเนินงาน

### 3.1 ขั้นตอนการดำเนินงาน
1. ศึกษาและวิเคราะห์ความต้องการของระบบ
2. ออกแบบ System Architecture
3. ออกแบบ Database Schema
4. พัฒนา Backend API (FastAPI)
5. พัฒนา Frontend (React + TypeScript)
6. พัฒนาระบบ AI Chat (LangGraph Multi-Agent)
7. ทดสอบระบบ
8. ปรับปรุงและสรุปผล

### 3.2 สถาปัตยกรรมระบบ (System Architecture)
- Client-Server Architecture
- Frontend ↔ Nginx (Reverse Proxy) ↔ FastAPI Backend ↔ PostgreSQL
- Backend ↔ LangGraph ↔ Multiple Agency APIs/MCP/A2A
- MCP Server สำหรับเปิดเผย Agency Metadata

### 3.3 การออกแบบฐานข้อมูล (Database Design)
- ตาราง User (admin/staff accounts)
- ตาราง Agency (หน่วยงานภาครัฐ + connection config)
- ตาราง Conversation (session การสนทนา)
- ตาราง Message (ข้อความแต่ละรายการ + feedback)
- ตาราง ConnectionLog (log การเชื่อมต่อ)

### 3.4 การออกแบบ API Endpoints
- Auth: login, signup, reset-password
- Chat: POST /chat (query → synthesized answer)
- Agencies: CRUD + test connection
- Conversations: list, delete, export
- Dashboard: stats, analytics
- Feedback: submit rating

### 3.5 การออกแบบ UI/UX
- Public Portal: Landing page, Agency cards, Chat interface
- Admin Portal: Sidebar navigation, Dashboard, Agency management, Chat, History

### 3.6 การทำงานของ AI Multi-Agent Routing
- Keyword-based agency detection (ภาษาไทย)
- LangGraph dynamic routing ตาม data_scope ของหน่วยงาน
- Parallel querying หลายหน่วยงานพร้อมกัน
- LLM synthesize คำตอบรวม

### 3.7 เครื่องมือที่ใช้ในการพัฒนา
- VS Code, Docker, Git, Node.js, Python, PostgreSQL

---

## บทที่ 4 ผลการดำเนินงาน

### 4.1 ผลการพัฒนาระบบ
- แสดงหน้าจอ Public Portal
- แสดงหน้าจอ Admin Login / Dashboard
- แสดงหน้าจอ Agency Management (CRUD)
- แสดงหน้าจอ Chat Interface + Agent Steps
- แสดงหน้าจอ Conversation History
- แสดงหน้าจอ Analytics Dashboard

### 4.2 ผลการทดสอบระบบ
- ทดสอบ Authentication (login/signup/JWT)
- ทดสอบ CRUD หน่วยงาน
- ทดสอบ Chat → Multi-Agent Routing → Answer Synthesis
- ทดสอบ Connection Test กับ Agency APIs
- ทดสอบ Feedback System
- ทดสอบ Responsive Design

### 4.3 ตัวอย่างการใช้งานจริง
- Scenario: ประชาชนถามคำถามเกี่ยวกับบริการภาครัฐ
- แสดง Flow ตั้งแต่ query → agent routing → agency APIs → synthesized answer

---

## บทที่ 5 สรุป อภิปรายผล และข้อเสนอแนะ

### 5.1 สรุปผลการดำเนินงาน
- สรุปตามวัตถุประสงค์แต่ละข้อ
- สรุปฟีเจอร์ที่พัฒนาสำเร็จ

### 5.2 อภิปรายผล
- ข้อดีของการใช้ Multi-Agent Routing เทียบกับ Single Agent
- ประสิทธิภาพของ Keyword-based detection vs LangGraph routing
- ความยืดหยุ่นของระบบรองรับ connection หลายรูปแบบ (API/MCP/A2A)
- ข้อจำกัดที่พบระหว่างการพัฒนา

### 5.3 ปัญหาและอุปสรรค
- ความท้าทายในการ route คำถามภาษาไทยไปยังหน่วยงานที่ถูกต้อง
- การจัดการ rate limit ของ API ภายนอก
- คุณภาพของคำตอบที่สังเคราะห์จาก LLM

### 5.4 ข้อเสนอแนะ
- เพิ่มระบบ RAG (Retrieval-Augmented Generation) สำหรับความแม่นยำ
- เพิ่ม Feedback Analytics Dashboard แบบละเอียด
- รองรับ Voice Input / Output
- เพิ่มระบบ Caching เพื่อลด latency
- รองรับภาษาอื่น ๆ นอกจากภาษาไทย

---

## ภาคผนวก (Appendix)
- ซอร์สโค้ดหลัก (บางส่วน)
- คู่มือการติดตั้งระบบ (Docker Compose)
- ตัวอย่าง API Request/Response
- ER Diagram
- System Architecture Diagram

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS, shadcn/ui |
| Backend | FastAPI, Python, Tortoise ORM |
| Database | PostgreSQL |
| AI/ML | LangChain, LangGraph, OpenAI API |
| Auth | JWT, Bcrypt |
| Infra | Docker, Nginx, FastMCP |
