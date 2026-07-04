import asyncio
import json
import random
import time
from datetime import timedelta
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.concurrency import spawn_logged
from app.config import settings
from app.models import Agency, ConnectionLog
from app.services.agency import test_connection
from app.services.agency_reconcile import reconcile_statuses
from app.services.analytics import regenerate_weekly_brief
from app.services.evaluation import run_evaluation
from app.services.log_sanitize import sanitize_body
from app.utils import generate_uuid, now

scheduler = AsyncIOScheduler()
sem: asyncio.Semaphore | None = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Opentelemetry auto-instrumentation
# ---------------------------------------------------------------------------
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

tracerProvider = TracerProvider(resource=Resource.create({SERVICE_NAME: "backend-scheduler"}))
tracerProvider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="jaeger:4317", insecure=True)))
tracer = tracerProvider.get_tracer(__name__)

async def _run_agency_item(agency: Agency) -> None:
    """Tracing + dispatch for a single agency health check (time-bounded by caller)."""
    with tracer.start_as_current_span(f"agency_chat_test {agency.name}") as span:
        span.set_attribute("agency.id", str(agency.id))
        span.set_attribute("agency.name", agency.name)
        try:
            if agency.status in ("draft", "disabled"):
                span.set_attribute("agency.skipped", True)
                return
            if agency.connection_type == "API":
                span.set_attribute("agency.connection_type", "API")
                scope = agency.data_scope or ["ทั่วไป"]
                scope = scope[random.randint(0, len(scope) - 1)] if scope else "ทั่วไป"
                span.set_attribute("agency.data_scope", scope)

                async with httpx.AsyncClient(timeout=settings.AGENCY_CHAT_TIMEOUT) as client:
                    headers = {"content-type": "application/json"}
                    for v in (agency.api_headers or []):
                        headers[v["name"].lower()] = v["value"]
                    span.set_attribute("agency.api_headers", json.dumps(headers))
                    span.set_attribute("agency.api_endpoint", agency.endpoint_url)

                    # POST-based probe. The "__query__" field is intentionally
                    # omitted so we can review how the agency handles a missing
                    # required field: any response at all is logged as success
                    # (the error status is inspected manually), and only a
                    # transport failure — no response — is treated as an error.
                    payload = {}
                    for k, v in (agency.expected_payload or {}).items():
                        if v == "__query__":
                            continue  # omit on purpose to probe the missing-field error
                        if v == "__user_id__":
                            payload[k] = str(generate_uuid())
                        elif v == "__session_id__":
                            payload[k] = str(generate_uuid())
                        elif v == "__conversation_id__":
                            payload[k] = str(generate_uuid())
                        else:
                            payload[k] = v
                    span.set_attribute("agency.api_payload", json.dumps(payload))

                    request_body = sanitize_body(json.dumps(payload))
                    response_body = ""
                    start_ns = time.perf_counter_ns()
                    try:
                        resp = await client.post(agency.endpoint_url, headers=headers, json=payload, timeout=settings.AGENCY_CHAT_TIMEOUT)
                        end_ns = time.perf_counter_ns()
                        latency = int((end_ns - start_ns) // 1_000_000)
                        span.set_attribute("agency.api_latency_ms", latency)
                        span.set_attribute("agency.api_status_code", resp.status_code)
                        span.set_attribute("agency.api_response", sanitize_body(resp.text, max_chars=500))
                        response_body = sanitize_body(resp.text)

                        # Known replies override the default HTTP-status behavior below.
                        # Extend this table as more agency responses are observed.
                        text = resp.text or ""
                        if "Message is required" in text:
                            # e.g. HTTP 400 to our deliberately-omitted field: the
                            # endpoint is alive and validating correctly -> success.
                            status = "success"
                        elif "Access token is invalid" in text:
                            # e.g. HTTP 401: endpoint is up but auth is broken -> error.
                            status = "error"
                        else:
                            # Default: let the HTTP status decide. Non-2xx raises
                            # httpx.HTTPStatusError, caught below and logged as error.
                            resp.raise_for_status()
                            status = "success"
                        detail = f"POST {agency.endpoint_url} -> {resp.status_code}\n\n{resp.text}"
                    # --- Example except checks ---
                    except httpx.HTTPStatusError as e:
                        # Raised only by resp.raise_for_status() above: a non-2xx
                        # response that no content rule whitelisted -> error.
                        end_ns = time.perf_counter_ns()
                        latency = int((end_ns - start_ns) // 1_000_000)
                        span.set_attribute("agency.api_latency_ms", latency)
                        span.set_attribute("agency.api_status_code", e.response.status_code)
                        status = "error"
                        detail = f"POST {agency.endpoint_url} -> {e.response.status_code} (non-2xx)\n\n{e.response.text}"
                    except httpx.TimeoutException:
                        end_ns = time.perf_counter_ns()
                        latency = int((end_ns - start_ns) // 1_000_000)
                        span.set_attribute("agency.api_latency_ms", latency)
                        status = "error"
                        detail = f"POST {agency.endpoint_url} timed out after {settings.AGENCY_CHAT_TIMEOUT}s"
                    except httpx.ConnectError as e:
                        end_ns = time.perf_counter_ns()
                        latency = int((end_ns - start_ns) // 1_000_000)
                        span.set_attribute("agency.api_latency_ms", latency)
                        status = "error"
                        detail = f"POST {agency.endpoint_url} connection failed: {e}"
                    except httpx.HTTPError as e:
                        # Catch-all for any other httpx transport-level failure.
                        end_ns = time.perf_counter_ns()
                        latency = int((end_ns - start_ns) // 1_000_000)
                        span.set_attribute("agency.api_latency_ms", latency)
                        status = "error"
                        detail = f"POST {agency.endpoint_url} failed: {e}"

                    await ConnectionLog.create(
                        id=str(generate_uuid()),
                        agency=agency,
                        action="test",
                        connection_type="API",
                        status=status,
                        latency_ms=latency,
                        detail=sanitize_body(detail),
                        request_body=request_body,
                        response_body=response_body,
                    )
            elif agency.connection_type in ("MCP", "A2A"):
                span.set_attribute("agency.connection_type", agency.connection_type)
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
            logger.error(f"Error testing agency {agency.name}: {e}")
            span.set_attribute("agency.error", str(e))


async def agency_chat_item(agency: Agency) -> None:
    logger.info(f"Testing agency {agency.name}...")
    async with sem:
        try:
            await asyncio.wait_for(_run_agency_item(agency), timeout=settings.AGENCY_CHAT_TIMEOUT + 5)
        except asyncio.TimeoutError:
            logger.error("agency %s health item timed out", agency.name)


async def agency_chat_test() -> None:
    logger.info("Running agency chat tests...")
    agencies = await Agency.all()
    await asyncio.gather(*[agency_chat_item(ag) for ag in agencies])
    try:
        await reconcile_statuses()
    except Exception as e:
        logger.error(f"Error reconciling agency statuses: {e}")


async def regenerate_brief_job() -> None:
    logger.info("Regenerating weekly brief...")
    try:
        await regenerate_weekly_brief()
    except Exception as e:
        logger.error(f"Error regenerating weekly brief: {e}")


async def purge_old_connection_logs() -> int:
    logger.info("Purging old connection logs...")
    cutoff = now() - timedelta(days=settings.CONNECTION_LOG_RETENTION_DAYS)
    return await ConnectionLog.filter(created_at__lt=cutoff).delete()


async def start_scheduler() -> None:
    global sem
    sem = asyncio.Semaphore(settings.AGENCY_CHAT_CONCURRENCY)
    spawn_logged(agency_chat_test(), name="agency_chat_test:startup")
    spawn_logged(regenerate_brief_job(), name="regenerate_brief_job:startup")
    scheduler.add_job(agency_chat_test, IntervalTrigger(minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES))
    scheduler.add_job(regenerate_brief_job, IntervalTrigger(hours=settings.BRIEF_REGEN_INTERVAL_HOURS))
    scheduler.add_job(purge_old_connection_logs, IntervalTrigger(hours=24))
    scheduler.add_job(run_evaluation, IntervalTrigger(hours=settings.EVAL_INTERVAL_HOURS))
    scheduler.start()
    logger.info("Scheduler started.")


async def stop_scheduler() -> None:
    scheduler.shutdown()
    logger.info("Scheduler stopped.")
