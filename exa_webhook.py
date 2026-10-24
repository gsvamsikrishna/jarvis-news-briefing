import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool


BASE_DIR = Path(__file__).resolve().parent
EVENTS_DB = Path(os.getenv("EXA_MONITOR_EVENTS_DB", BASE_DIR / "data" / "exa-monitor-events.sqlite3"))
MAX_BODY_BYTES = 2 * 1024 * 1024
logger = logging.getLogger("exa_webhook")

app = FastAPI(
    title="Exa Monitor Webhook Receiver",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def verify_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    fields: dict[str, str] = {}
    for part in signature_header.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator or key in fields:
            return False
        fields[key] = value

    timestamp = fields.get("t", "")
    signature = fields.get("v1", "")
    if not timestamp.isdigit() or not re.fullmatch(r"[0-9a-fA-F]{64}", signature):
        return False

    signed_payload = timestamp.encode("ascii") + b"." + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def _store_event(event: dict[str, Any]) -> bool:
    data = event.get("data")
    data = data if isinstance(data, dict) else {}
    event_id = event["id"]
    serialized_event = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    received_at = datetime.now(timezone.utc).isoformat()

    EVENTS_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(EVENTS_DB, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS exa_monitor_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                monitor_id TEXT,
                run_id TEXT,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO exa_monitor_events
                (event_id, event_type, monitor_id, run_id, received_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event.get("type", ""),
                data.get("monitorId"),
                data.get("id"),
                received_at,
                serialized_event,
            ),
        )
        return cursor.rowcount == 1


async def _read_bounded_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Webhook payload is too large.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from exc

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    return bytes(body)


@app.get("/healthz", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/exa")
async def receive_exa_monitor_event(request: Request) -> JSONResponse:
    secret = os.getenv("EXA_MONITOR_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("EXA_MONITOR_WEBHOOK_SECRET is not configured.")
        raise HTTPException(status_code=503, detail="Webhook receiver is not configured.")

    signature = request.headers.get("exa-signature", "")
    body = await _read_bounded_body(request)
    if not signature or not verify_signature(body, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid Exa webhook signature.")

    try:
        event = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be valid JSON.") from exc
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object.")
    if not isinstance(event.get("id"), str) or not event["id"] or len(event["id"]) > 200:
        raise HTTPException(status_code=400, detail="Webhook event must include a valid event ID.")
    if not isinstance(event.get("type"), str) or not event["type"]:
        raise HTTPException(status_code=400, detail="Webhook event must include a type.")

    try:
        inserted = await run_in_threadpool(_store_event, event)
    except sqlite3.Error:
        logger.exception("Could not store verified Exa Monitor event %s.", event["id"])
        raise HTTPException(status_code=500, detail="Could not store the Exa webhook event.") from None
    except OSError:
        logger.exception("Could not access Exa Monitor event storage for event %s.", event["id"])
        raise HTTPException(status_code=500, detail="Could not store the Exa webhook event.") from None

    logger.info(
        "%s verified Exa Monitor event %s (%s).",
        "Stored" if inserted else "Acknowledged duplicate",
        event["id"],
        event["type"],
    )
    return JSONResponse(
        {"received": True, "duplicate": not inserted},
        status_code=200,
    )
