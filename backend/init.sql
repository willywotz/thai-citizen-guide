-- Thai Citizen Guide - PostgreSQL Schema
-- Run once on first startup

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (replaces Supabase Auth + profiles + user_roles)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    avatar_url TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agencies table
CREATE TABLE IF NOT EXISTS agencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    short_name VARCHAR(100),
    logo VARCHAR(10),
    connection_type VARCHAR(50) DEFAULT 'API',
    status VARCHAR(50) DEFAULT 'active',
    description TEXT,
    data_scope TEXT[],
    total_calls INTEGER DEFAULT 0,
    color VARCHAR(100),
    endpoint_url TEXT,
    api_key_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) DEFAULT 'สนทนาใหม่',
    preview TEXT,
    agencies TEXT[],
    status VARCHAR(50) DEFAULT 'success',
    message_count INTEGER DEFAULT 0,
    response_time VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    agent_steps JSONB,
    sources JSONB,
    rating VARCHAR(10),
    feedback_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

-- Connection logs table
CREATE TABLE IF NOT EXISTS connection_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    action VARCHAR(100),
    connection_type VARCHAR(50),
    status VARCHAR(50),
    latency_ms INTEGER,
    detail TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_connection_logs_agency_id ON connection_logs(agency_id);

-- Seed default agencies
INSERT INTO agencies (name, short_name, logo, connection_type, status, description, data_scope, color, endpoint_url)
VALUES
    (
        'สำนักงานคณะกรรมการอาหารและยา',
        'อย.',
        '🏥',
        'MCP',
        'active',
        'ตรวจสอบทะเบียนยา อาหาร และเครื่องสำอาง',
        ARRAY['ยา', 'อาหาร', 'เครื่องสำอาง', 'ผลิตภัณฑ์สุขภาพ'],
        'hsl(145 55% 40%)',
        'https://api.fda.moph.go.th'
    ),
    (
        'กรมสรรพากร',
        'สรรพากร',
        '💰',
        'A2A',
        'active',
        'ข้อมูลภาษีเงินได้ ภาษีมูลค่าเพิ่ม และการยื่นแบบ',
        ARRAY['ภาษีเงินได้', 'VAT', 'ลดหย่อนภาษี', 'ยื่นแบบออนไลน์'],
        'hsl(213 70% 45%)',
        'https://api.rd.go.th'
    ),
    (
        'กรมการปกครอง',
        'ปกครอง',
        '🏛️',
        'API',
        'active',
        'ทะเบียนราษฎร บัตรประชาชน และเอกสารพลเมือง',
        ARRAY['บัตรประชาชน', 'ทะเบียนบ้าน', 'แจ้งเกิด-ตาย', 'เปลี่ยนชื่อ'],
        'hsl(25 85% 55%)',
        'https://api.dopa.go.th'
    ),
    (
        'กรมที่ดิน',
        'ที่ดิน',
        '🗺️',
        'MCP',
        'active',
        'โฉนดที่ดิน การจดทะเบียน และราคาประเมิน',
        ARRAY['โฉนดที่ดิน', 'ราคาประเมิน', 'รังวัด', 'จดทะเบียนสิทธิ'],
        'hsl(280 50% 50%)',
        'https://api.dol.go.th'
    )
ON CONFLICT DO NOTHING;

-- Create default admin user (password: admin1234)
-- bcrypt hash of "admin1234"
INSERT INTO users (email, hashed_password, display_name, is_admin)
VALUES ('admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/oIzxlsVSq', 'Admin', TRUE) ON CONFLICT DO NOTHING;
