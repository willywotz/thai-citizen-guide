

# User Management for API (REST) Agency Connections — Hybrid Approach

## Overview

Enhance the Agency form for `API (REST)` connection type with both manual fields and an optional LLM-powered API spec parser. When connection type is API, show additional configuration fields. Optionally allow uploading an OpenAPI/Swagger JSON/YAML file to auto-fill those fields via LLM.

## Database Changes

Add columns to `agencies` table:

```sql
ALTER TABLE public.agencies
  ADD COLUMN IF NOT EXISTS auth_method text DEFAULT 'api_key',
  ADD COLUMN IF NOT EXISTS auth_header text DEFAULT '',
  ADD COLUMN IF NOT EXISTS base_path text DEFAULT '',
  ADD COLUMN IF NOT EXISTS rate_limit_rpm integer DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS request_format text DEFAULT 'json',
  ADD COLUMN IF NOT EXISTS api_endpoints jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS api_spec_raw text DEFAULT NULL;
```

`api_endpoints` stores parsed endpoint definitions:
```json
[
  { "method": "GET", "path": "/search", "description": "ค้นหาข้อมูล" },
  { "method": "POST", "path": "/verify", "description": "ตรวจสอบเอกสาร" }
]
```

## UI Changes — AgencyFormDialog

When `connectionType === 'API'`, render additional fields below endpoint URL:

1. **Auth Method** — Select: `api_key` | `oauth2` | `basic_auth` | `none`
2. **Auth Header Name** — Input (e.g. `X-API-Key`, `Authorization`)
3. **Base Path** — Input (e.g. `/api/v1`)
4. **Rate Limit** — Number input (requests per minute, optional)
5. **Request Format** — Select: `json` | `xml`
6. **API Endpoints** — Editable list (method + path + description), add/remove rows
7. **Upload API Spec** — File upload button (accepts `.json`, `.yaml`) with "Auto-fill from spec" action

## Edge Function: `parse-api-spec`

New edge function that:
1. Receives raw OpenAPI/Swagger spec text
2. Sends to Lovable AI (gemini-3-flash-preview) with a structured tool call to extract:
   - auth method & header
   - base path
   - list of endpoints (method, path, description)
   - rate limit info
3. Returns structured JSON to populate the form

## Agency Type Updates

Extend `Agency` interface and `AgencyRow` with the new fields. Update `mapRowToAgency`.

## Implementation Steps

1. **Database migration** — Add new columns
2. **Update types** — Extend Agency/AgencyRow interfaces
3. **Create `parse-api-spec` edge function** — LLM-based spec parser
4. **Update AgencyFormDialog** — Conditional API fields + spec upload
5. **Update `agency-manage` edge function** — Handle new fields in create/update
6. **Update AgencyDetailPage** — Display API config details

