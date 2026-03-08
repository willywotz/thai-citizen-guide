from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import auth, agencies, conversations, dashboard, feedback, chat, ws

app = FastAPI(title="Thai Citizen Guide API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agencies.router)
app.include_router(conversations.router)
app.include_router(dashboard.router)
app.include_router(feedback.router)
app.include_router(chat.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
