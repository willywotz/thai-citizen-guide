import asyncio
import json
import random
import time

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.models import Agency, ConnectionLog
from app.utils import generate_uuid, now

scheduler = AsyncIOScheduler()
sem: asyncio.Semaphore | None = None


async def agency_chat_item(agency: Agency) -> None:
    try:
        async with sem:
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
                        detail=f"Query: {payload.get('query', '')}\n\nAnswer: {resp.text}",
                        request_body=json.dumps(payload),
                        response_body=resp.text,
                    )
    except Exception as e:
        print(f"Error testing agency {agency.name}: {e}")


async def agency_chat_test() -> None:
    agencies = await Agency.all()
    await asyncio.gather(*[agency_chat_item(ag) for ag in agencies])


async def start_scheduler() -> None:
    global sem
    sem = asyncio.Semaphore(settings.AGENCY_CHAT_CONCURRENCY)
    asyncio.create_task(agency_chat_test())
    scheduler.add_job(agency_chat_test, IntervalTrigger(minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES))
    scheduler.start()


async def stop_scheduler() -> None:
    scheduler.shutdown()
