"""Reference agency endpoint for the Thai Citizen Guide gateway.

Implements the API connection contract: accept a JSON POST whose body shape is
declared via the agency's expected_payload template, and reply 200 JSON within
the gateway timeout.
Run: uvicorn main:app --port 9000
"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Reference Agency")


class ChatIn(BaseModel):
    query: str
    session_id: str | None = None


@app.post("/chat")
async def chat(body: ChatIn):
    return {
        "answer": f"(ตัวอย่าง) ได้รับคำถาม: {body.query}",
        "sources": [{"title": "คู่มือประชาชน", "url": "https://example.go.th/guide"}],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
