# Reference Agency

A minimal FastAPI server that satisfies the Thai Citizen Guide gateway's API
connection contract. Use it to test your local gateway setup or as a starting
point for a real agency integration.

## Requirements

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.0.0
```

Install them:

```bash
pip install "fastapi>=0.110.0" "uvicorn[standard]>=0.29.0" "pydantic>=2.0.0"
```

## Run

```bash
uvicorn main:app --port 9000
```

The server exposes two endpoints:

| Method | Path      | Purpose                                        |
|--------|-----------|------------------------------------------------|
| POST   | `/chat`   | Receives a question and returns an answer      |
| GET    | `/health` | Returns `{"status": "ok"}` for health probes  |

## Register in the gateway

When creating an agency record, set:

| Field              | Value                                          |
|--------------------|------------------------------------------------|
| `connection_type`  | `API`                                          |
| `endpoint_url`     | `http://localhost:9000/chat`                   |
| `expected_payload` | `{"query": "__query__", "session_id": "__session_id__"}` |

The gateway substitutes `__query__` with the citizen's sub-question and
`__session_id__` with the conversation ID (or a generated UUID when no session
exists) before POSTing to `endpoint_url`.

See `docs/agency-integration.md` for the full integration guide.
