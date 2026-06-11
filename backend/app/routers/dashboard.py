"""
Dashboard stats route — port of the Supabase `dashboard-stats` edge function.

Endpoint
--------
  GET  /dashboard/stats
"""

import time

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.analytics import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", summary="Get dashboard statistics and charts data")
async def dashboard_stats(user: User = Depends(get_current_user)) -> dict:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่สามารถเข้าถึงข้อมูลนี้ได้")

    start = time.time()
    data = await get_dashboard_stats()
    return {"success": True, "data": data, "responseTime": int((time.time() - start) * 1000)}
