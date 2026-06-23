# สรุปการปรับปรุงระบบ: Work → Right → Fast (2026-06-23)

> PR #60 (merged เข้า `dev`, merge commit `6b91eed`) — ปรับปรุงทั้งระบบตามแนวทาง
> **"ทำให้ใช้งานได้ → ทำให้ถูกต้อง → ทำให้เร็ว" (make it work → make it right → make it fast)**
> รวม 61 commits, ~163 ไฟล์, +10,190 / −2,014 บรรทัด ครอบคลุม 4 ส่วน: backend, frontend, agent-proxy, system/CI
>
> เอกสารสเปก/แผนงานทั้งหมด: `docs/superpowers/specs/2026-06-23-*` และ `docs/superpowers/plans/2026-06-23-*`

---

## สรุปย่อ (Short note / TL;DR)

ปรับปรุงทั้ง 4 ส่วนของระบบแบบทีละงาน (แต่ละงานมีการรีวิวและแก้ไขแยกกัน + รีวิวรวมทั้ง branch ตอนท้าย):

- **Backend** — แก้บั๊กความถูกต้องที่เคยเงียบ (silent failures), บันทึก conversation เป็น `failed` เมื่อไม่พบหน่วยงาน/คำตอบว่าง, ตรวจสอบ JSON จาก LLM, rate limiter เปลี่ยนจาก "ปล่อยผ่านทั้งหมด" เป็น "จำกัดแบบ in-process" เมื่อ Redis ล่ม, แยกไฟล์ที่ใหญ่เกินไปเป็น package, และเพิ่มความเร็ว query หลายจุด (N+1 → grouped, similarity 3 query → join เดียว, cache, index, pool)
- **Frontend** — เพิ่ม error/retry state ทุกหน้า (ไม่ค้างที่ skeleton เมื่อโหลดล้มเหลว), ใส่ timeout ให้ SSE, ตรวจสอบฟอร์มด้วย zod, แยก god components, ทำ code-splitting (1 bundle → 82 chunks), memoization, ย้าย filter/paginate ไปฝั่ง server, และ **ตอนนี้รัน unit test (vitest) ใน CI แล้ว** (เดิมไม่เคยรัน)
- **agent-proxy (Go)** — กำจัด panic ใน hot path, ส่งต่อ error ที่เคยถูกกลืน, เพิ่ม in-memory cache ของ agency (TTL), stream response แทน double-buffer, ปรับ HTTP transport
- **System/CI** — รัน frontend test + coverage ใน CI, cache dependency (uv/go), ย้าย credential ทดสอบไปเป็น secrets, รัน e2e ตอน PR เข้า `dev`, ทำ config ให้ override ผ่าน env ได้, เพิ่ม **pre-deploy gate** (deploy ต้องผ่าน test + e2e ก่อน)

**ผลทดสอบ (ทั้งหมดผ่าน):** backend `pytest` 433 ผ่าน / 4 skip · frontend `vitest` ผ่าน (รันใน CI แล้ว) · agent-proxy `go test` ผ่าน · `blackbox-e2e` (สร้าง stack จริงบน Postgres → seed admin → ทดสอบ API + UI) ผ่าน

**⚠️ สิ่งที่ต้องทำต่อ (ฝั่งผู้ดูแลระบบ):** เปลี่ยน (rotate) **OpenRouter API key** เพราะ key เดิมเคยถูก commit ลง repo

---

## การเปลี่ยนแปลงเชิงพฤติกรรม (Behavior changes) — สำคัญ

สิ่งเหล่านี้เปลี่ยน "พฤติกรรมที่สังเกตเห็นได้" ของระบบ ไม่ใช่แค่ปรับโครงสร้างภายใน:

1. **สถานะ conversation เป็น `failed` ได้แล้ว** — เดิมทุกครั้งบันทึกเป็น `success` เสมอ ตอนนี้ถ้า route/dispatch ล้มเหลว หรือคำตอบที่สังเคราะห์ได้ว่างเปล่า จะบันทึกเป็น `failed` (เห็นได้ผ่าน `GET /conversations`) และ conversation ที่ `failed` จะไม่ถูกนำกลับมาใช้ใน similarity cache (กันไม่ให้คำตอบเสียไป poison cache)
2. **Router LLM JSON ที่ผิดรูปแบบไม่ทำให้ 500 อีกต่อไป** — ถ้า LLM ตอบ JSON ไม่ถูกต้องหรือไม่มี key `routes` จะ fallback เป็น "ไม่มี route" แทนที่จะ error ทั้งคำขอ
3. **Rate limiter เมื่อ Redis ล่ม** — เดิม "ปล่อยผ่านทุกคำขอ" (fail-open, เสี่ยงถูกยิงถล่ม) ตอนนี้ **ลดระดับไปใช้ in-process limiter** (จำกัดต่อ worker) พร้อม log/observability แจ้งเตือนสถานะ degraded
4. **งานเบื้องหลัง (fire-and-forget)** — เดิมใช้ `asyncio.create_task(...)` ที่กลืน exception เงียบ ๆ ตอนนี้ใช้ helper `spawn_logged` ที่ log error เสมอ และ health-check ของแต่ละ agency มี timeout ต่อรายการ ไม่ให้ตัวที่ช้าค้างตัวอื่น
5. **Config override ที่ไม่รู้จัก** — `apply_overrides` จะรายงาน/log key ที่ไม่รู้จักหรือค่าผิด แทนที่จะกลืนเงียบ ๆ (กัน typo ใน env)
6. **Frontend แสดง error อย่างชัดเจน** — หน้าใด ๆ ที่โหลดข้อมูลล้มเหลวจะแสดง error + ปุ่ม retry แทนที่จะค้างที่ skeleton ตลอดไป; การ stream chat ที่ค้างจะ timeout แล้วแสดง "การเชื่อมต่อหลุด"

> **หมายเหตุ:** ไม่มีการเปลี่ยน "รูปร่าง" ของ request/response ของ public API (`/api`) แบบ breaking — พารามิเตอร์ใหม่เป็นแบบ additive (ใส่หรือไม่ใส่ก็ได้ พฤติกรรมเดิมคงอยู่)

---

## รายละเอียดทั้งหมด (Full detail)

### 1) Backend (Python / FastAPI / Tortoise ORM)

**กลุ่ม Work — ความถูกต้อง**
- `save_turn` ใหม่ที่บันทึก conversation + message ภายใน **transaction เดียว** (กันข้อมูลค้างครึ่ง ๆ กลาง ๆ) และคำนวณสถานะ `success`/`failed` จากผลลัพธ์จริง (BC #1, #3)
- ตรวจสอบ JSON ที่ได้จาก router LLM ก่อนใช้งาน — ผิดรูปแบบ → fallback เป็นไม่มี route (BC #2)
- เพิ่ม `app/concurrency.py:spawn_logged` แทน `asyncio.create_task` ที่กลืน error — ใช้ใน chat และ scheduler (BC #3)
- Rate limiter (`services/rate_limit.py`) เมื่อ Redis ใช้ไม่ได้ → ลดระดับเป็น in-process limiter + observability แทน fail-open (BC #4)
- `config.apply_overrides` รายงาน key ที่ไม่รู้จัก/ค่าผิด (BC #5) และลบ `except:` แบบ bare ออก (เปลี่ยนเป็น `except Exception:`) (BC #6)
- scheduler ใส่ timeout ต่อ agency แต่ละราย + ใช้ semaphore อย่างปลอดภัย

**กลุ่ม Right — โครงสร้าง (ไม่เปลี่ยนพฤติกรรม)**
- แยก `routers/agencies.py` → package `routers/agencies/` (crud / lifecycle / owners / golden / spec) โดย **path และลำดับการ register เหมือนเดิมทุกประการ**
- แยก `services/analytics.py` → package `services/analytics/` (dashboard / health / brief) พร้อม re-export เพื่อ import เดิมยังใช้ได้
- รวม logic การบันทึกของ `/chat/external` และ `/chat/stream` เข้ามาที่ `save_turn` (ลดโค้ดซ้ำ)
- ทำให้ graph รับ agency loader แบบ inject ได้ และแก้การ default id ใน MCP ให้ค่าเดียวกันทั้ง response

**กลุ่ม Fast — ประสิทธิภาพ**
- `public_status`: เดิม query นับต่อ agency (N+1) → รวมเป็น **grouped query เดียว**
- similarity: เดิม 3 query → รวมเป็น **join เดียว** (และผูกกับ conversation ที่ถูกต้อง + กรอง `status='success'` ใน SQL)
- agency directory: ทำ **in-memory cache (TTL)** + invalidate เมื่อมีการแก้ไข + กรอง agency ด้วย keyword ก่อนใส่ใน prompt ของ router (ไม่ยัด agency ทั้งหมด)
- embedding: เพิ่ม **TTL cache** ต่อ query (พร้อม copy-on-read กันการแก้ไข object ใน cache โดยไม่ตั้งใจ)
- DB: เพิ่ม **index** ของคอลัมน์ที่ใช้บ่อย + ตั้งค่า **connection pool (asyncpg)** ผ่าน config แบบ dict ที่รักษา `sslmode`/รหัสผ่านที่ encode ไว้ และเลือก placeholder ตาม dialect (`$1` สำหรับ Postgres / `?` สำหรับ SQLite ในการทดสอบ)
- `analytics.get_agency_health`: รวม query ต่อ agency เป็น grouped query
- **เพิ่มพารามิเตอร์ฝั่ง server แบบ additive:** `GET /api/v1/conversations` รับ `date_from`/`date_to`/`page`/`page_size`; `GET /api/v1/connection-logs` รับ `status`/`connection_type` (ใช้คู่กับ frontend)

---

### 2) Frontend (React / TypeScript / Vite)

**กลุ่ม Work**
- คอมโพเนนต์กลาง `QueryStateBoundary` จัดการสถานะ loading / error (มีปุ่ม retry, มี `role="alert"`) / empty ที่แยกจาก error อย่างชัดเจน — นำไปใช้ที่หน้า Health, Heatmap, Dashboard, Feedback, Connection-logs (เดิมหน้าพวกนี้ค้าง skeleton เมื่อโหลดล้มเหลว)
- การ stream chat (SSE) มี **idle timeout** — ถ้า stream ค้างจะ `cancel` reader แล้วแสดงสถานะการเชื่อมต่อหลุด ไม่ค้างค้างตลอดไป
- ฟอร์มสร้าง/แก้ไข agency ตรวจสอบด้วย **zod** (URL, ชื่อ header) พร้อมข้อความ error แบบ inline ทั้งใน wizard และหน้า edit

**กลุ่ม Right**
- แยก god components: `ApiKeysPage` → dialog ย่อย + list; `useChat` → `useChatStream` (จัดการ SSE) + ส่วนจัดการ state
- ดึง `FieldInput` และ `ChartTooltip` (มี type ชัดเจน แทน `any`) ออกมาใช้ร่วม
- รวมค่าคงที่ที่กระจัดกระจาย (page size, refetch interval, status label) ไว้ที่ `shared/constants/`
- เพิ่ม hook `usePaginatedFilter` (ภายหลังถูกแทนที่ด้วยการ filter ฝั่ง server จึงลบทิ้ง)

**กลุ่ม Fast**
- **Route-based code-splitting** ด้วย `React.lazy` + `Suspense` — จาก bundle เดียวเป็น **82 chunks** (โหลดหน้าแรกเบาลง)
- `React.memo` + `useCallback`/`useMemo` ให้คอมโพเนนต์ที่ render บ่อย (MessageBubble, AgencyCard, DashboardStatsRow)
- หน้า History และ Connection-logs ย้ายไป filter/paginate **ฝั่ง server** (ใช้พารามิเตอร์ใหม่จาก backend) แทนการดึงทั้งหมดมา filter ฝั่ง client

**CI**
- ไฟล์ test (vitest, 30+ ไฟล์ ใช้ MSW) **ถูกรันใน CI แล้ว** พร้อม coverage แบบรายงานอย่างเดียว (เดิม CI รันแค่ `tsc --noEmit`)

---

### 3) agent-proxy (Go)

- **กำจัด panic ใน hot path:** `uuidV7` คืนค่า error แทน panic; โหลด `time.LoadLocation("Asia/Bangkok")` ครั้งเดียวตอน init แทนทุก request
- **ส่งต่อ error ที่เคยถูกกลืน:** อ่าน body request ล้มเหลว → 400; stream response ล้มเหลว → log + บันทึกใน span; การเขียน connection log ล้มเหลว → บันทึกใน span (เพื่อ audit)
- **agency TTL cache (`cache.go`):** ลด query Postgres ทุก request, ปลอดภัยต่อ concurrency (`sync.RWMutex`), invalidate ได้, และ **ไม่ cache กรณีไม่พบข้อมูล (`pgx.ErrNoRows`)** เพื่อให้ agency ใหม่ใช้งานได้ทันที
- **Stream response** ตรงไปยัง client แทน double-buffer + จำกัดขนาด body ที่เก็บลง span/log (~8 KiB)
- ปรับ `http.Transport` (`MaxIdleConns`/`MaxIdleConnsPerHost`)
- HTTP contract ของ `/agent-proxy/{uuid}` คงเดิม (backward-compatible)

---

### 4) System / CI / Infra

- **รัน frontend vitest + coverage ใน CI** (ต่อยอดจากที่เริ่มไว้)
- **Cache dependency** ใน CI: uv (backend) และ go modules/build (agent-proxy) — CI เร็วขึ้น
- **ย้าย credential ทดสอบไปเป็น GitHub secrets** (`E2E_ADMIN_EMAIL`/`E2E_ADMIN_PASSWORD`/`E2E_TEST_USER_PASSWORD`) พร้อม step "ตรวจสอบ secret" ที่ fail เร็วและมีข้อความชัดเจนเมื่อยังไม่ได้ตั้งค่า
- **รัน full-stack e2e sweep ตอน PR เข้า `dev`** (เดิมรันเฉพาะ PR เข้า `main`)
- **Config ฝั่ง prod override ผ่าน env ได้** + ไฟล์ตัวอย่าง `.env.prod.example`
- **เอกสาร routing ของ nginx:** ชี้แจงบทบาทของ `default.conf` (gateway) กับ `frontend/nginx.conf` (SPA server) ว่าคนละหน้าที่กัน ไม่ใช่ของซ้ำ
- **มาตรฐาน healthcheck** ของ service ใน docker-compose (ใช้ `127.0.0.1`, ตั้งเวลาให้สอดคล้องกัน)
- **Pre-deploy gate:** job `deploy` ต้อง `needs: [test, e2e]` — merge เข้า `main` จะ deploy ได้ก็ต่อเมื่อ test + e2e ผ่าน (เดิม deploy โดยไม่มีด่านตรวจ)
  - หมายเหตุ: ภายหลังได้ปรับ deploy ให้เรียบง่ายขึ้น — เขียน `.env` ขั้นต่ำ (`ENV`, port, `JWT_SECRET`, `OPENROUTER_API_KEY`) ส่วนค่าอื่น (Postgres/CORS/frontend/OneChat/MCP) ใช้ค่า default ของ Compose/โค้ด

---

## เรื่องเด่นที่ระบบทดสอบจับได้ (กรณีศึกษา)

ด่าน **pre-deploy e2e ที่เพิ่มใหม่ในงานนี้ช่วยจับบั๊กจริงทันที**: backend startup ล้มเหลวบน Postgres จริง (`zlib.error: invalid distance too far back`) เพราะไฟล์ migration index (จาก task เพิ่ม DB index) มีค่า `MODELS_STATE` ที่เสียหาย

- สาเหตุ: migration นั้นเพิ่มแค่ index (raw SQL) ไม่ได้เปลี่ยน model จึงต้องใช้ `MODELS_STATE` เดียวกับ migration ก่อนหน้า แต่ตอนสร้างกลับได้ค่าที่เสีย
- ทำไม unit test ไม่จับ: ชุดทดสอบใช้ SQLite ผ่าน `Tortoise.init`/`generate_schemas` ซึ่ง **ไม่อ่านไฟล์ migration ของ aerich เลย** — บั๊กนี้จึงโผล่เฉพาะตอนรัน aerich + Postgres จริง (ซึ่งคือสิ่งที่ด่าน e2e ทำ)
- การแก้: คัดลอก `MODELS_STATE` จาก migration ก่อนหน้า (ที่ถูกต้อง) มาใส่ (commit `daa09f8`) — ตรวจสอบแล้วว่า decompress ได้ และทดสอบ stack ขึ้นได้ทั้งบน CI และเครื่อง local

---

## วิธีทำงานของงานนี้ (Process)

- ทำทีละ task ตามแผนใน `docs/superpowers/plans/2026-06-23-*`
- แต่ละ task: เขียน characterization/TDD test ก่อน → implement → รีวิวแยก (ตรวจ spec + คุณภาพโค้ด) → แก้ตาม finding → รีวิวซ้ำ
- ปิดท้ายด้วยการรีวิวรวมทั้ง branch (ไม่มี blocker) แล้วทำความสะอาดเล็กน้อย
- รวมทุกอย่างไว้ใน PR เดียว (#60) เข้า `dev`

---

## สิ่งที่ต้องทำต่อ (Action items)

- [ ] **เปลี่ยน (rotate) OpenRouter API key** — key เดิมเคยถูก commit ลง repo จึงควร revoke ของเดิมที่ฝั่ง OpenRouter และอัปเดตค่า secret ใหม่
- [x] ตั้งค่า GitHub secrets สำหรับ e2e (`E2E_ADMIN_EMAIL` = `admin@example.com`, `E2E_ADMIN_PASSWORD` = `admin1234`, `E2E_TEST_USER_PASSWORD` = สร้างใหม่แล้ว) — เรียบร้อย
- [x] ตั้งค่า secret prod ที่จำเป็น (`JWT_SECRET`, `OPENROUTER_API_KEY`) — มีอยู่แล้ว
- [ ] (ถ้าต้องการขึ้น prod) เปิด PR จาก `dev` → `main` เพื่อ promote (deploy จะรันก็ต่อเมื่อผ่านด่าน test + e2e)
