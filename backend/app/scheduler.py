import asyncio
import json
import random
import time

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.models import Agency, ConnectionLog
from app.services.agency import test_connection
from app.services.agency_reconcile import reconcile_statuses
from app.services.analytics import regenerate_weekly_brief
from app.services.log_sanitize import sanitize_body
from app.utils import generate_uuid, now

scheduler = AsyncIOScheduler()
sem: asyncio.Semaphore | None = None


async def agency_chat_item(agency: Agency) -> None:
    try:
        async with sem:
            if agency.status in ("draft", "disabled"):
                return
            if agency.connection_type == "API":
                scope = agency.data_scope or ["ทั่วไป"]
                scope = scope[random.randint(0, len(scope) - 1)] if scope else "ทั่วไป"

                async with httpx.AsyncClient(timeout=settings.AGENCY_CHAT_TIMEOUT) as client:
                    headers = {"content-type": "application/json"}
                    for v in (agency.api_headers or []):
                        headers[v["name"].lower()] = v["value"]
                    payload = {}
                    for k, v in (agency.expected_payload or {}).items():
                        payload[k] = v
                        if v == "__query__":
                            payload[k] = "ปรึกษากฎหมาย" + scope
                        if v == "__user_id__":
                            payload[k] = str(generate_uuid())
                        if v == "__session_id__":
                            payload[k] = str(generate_uuid())
                        if v == "__conversation_id__":
                            payload[k] = str(generate_uuid())
                    start_ns = time.perf_counter_ns()
                    resp = await client.post(agency.endpoint_url, headers=headers, json=payload)
                    end_ns = time.perf_counter_ns()
                    latency = int((end_ns - start_ns) // 1_000_000)
                    await ConnectionLog.create(
                        id=str(generate_uuid()),
                        agency=agency,
                        action="test",
                        connection_type="API",
                        status="success" if resp.status_code == 200 else "error",
                        latency_ms=latency,
                        detail=sanitize_body(f"Query: {payload.get('query', '')}\n\nAnswer: {resp.text}"),
                        request_body=sanitize_body(json.dumps(payload)),
                        response_body=sanitize_body(resp.text),
                    )
            elif agency.connection_type in ("MCP", "A2A"):
                result = await test_connection(agency.connection_type, agency)
                try:
                    latency = int(str(result.get("latency", "0")).rstrip("ms"))
                except ValueError:
                    latency = 0
                await ConnectionLog.create(
                    id=str(generate_uuid()),
                    agency=agency,
                    action="test",
                    connection_type=agency.connection_type,
                    status="success" if result.get("success") else "error",
                    latency_ms=latency,
                    detail=sanitize_body(result.get("error") or "ok"),
                )
    except Exception as e:
        print(f"Error testing agency {agency.name}: {e}")


async def agency_chat_test() -> None:
    agencies = await Agency.all()
    await asyncio.gather(*[agency_chat_item(ag) for ag in agencies])
    try:
        await reconcile_statuses()
    except Exception as e:
        print(f"Error reconciling agency statuses: {e}")


async def regenerate_brief_job() -> None:
    try:
        await regenerate_weekly_brief()
    except Exception as e:
        print(f"Error regenerating weekly brief: {e}")


async def start_scheduler() -> None:
    global sem
    sem = asyncio.Semaphore(settings.AGENCY_CHAT_CONCURRENCY)
    asyncio.create_task(agency_chat_test())
    asyncio.create_task(regenerate_brief_job())
    scheduler.add_job(agency_chat_test, IntervalTrigger(minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES))
    scheduler.add_job(regenerate_brief_job, IntervalTrigger(hours=settings.BRIEF_REGEN_INTERVAL_HOURS))
    scheduler.start()


async def stop_scheduler() -> None:
    scheduler.shutdown()
