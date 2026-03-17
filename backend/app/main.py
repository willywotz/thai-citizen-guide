from fastapi import FastAPI, Depends
from .db import get_db
from .models import User as UserModel, Agency as AgencyModel

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}
