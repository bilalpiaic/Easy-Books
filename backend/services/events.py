"""Outgoing webhook / event bus (#114).

Design (mirrors the #113 no-Redis constraint — this app also ships as an
offline Electron / script install, so there is no external queue):

- `emit()` is called from inside a request handler's open transaction. It
  only WRITES `WebhookDelivery` outbox rows — one per active endpoint
  subscribed to the event — and never performs network I/O. The rows commit
  (or roll back) atomically with the business document itself.
- The FastAPI lifespan runs `delivery_loop()` (see main.py), which drains
  due rows: instantly after an emit (a threadsafe wake on the loop's
  asyncio.Event) and every POLL_SECONDS as a fallback for retries and rows
  written by processes that can't reach the loop (scripts, tests).
- Each send is signed `X-EasyBooks-Signature: sha256=<HMAC-SHA256(secret,
  raw-body)>` so receivers can verify authenticity.
- Failures retry at 1m, 5m, 30m, 2h, 24h (RETRY_DELAYS); after MAX_ATTEMPTS
  the row is marked `failed` and shows up in the Settings delivery log.

Testing seams: `drain_once(post=...)` accepts an injectable POST callable,
and `_utcnow()` is patchable for retry-schedule tests.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx
from sqlmodel import Session, select

from models import WebhookDelivery, WebhookEndpoint

EVENT_TYPES = [
    "invoice.created", "invoice.paid", "invoice.voided",
    "bill.created", "bill.paid",
    "payment.received", "payment.made",
    "customer.created", "vendor.created",
    "period.closed",
    "stock.low",
    "employee.created",
]

RETRY_DELAYS = [60, 300, 1800, 7200, 86400]   # seconds after 1st..5th failure
MAX_ATTEMPTS = len(RETRY_DELAYS)
POLL_SECONDS = 30
BATCH_SIZE = 25
TIMEOUT_SECONDS = 10.0

# Wake plumbing: the lifespan loop registers its event loop + Event here so
# emit() (running in a request threadpool worker) can nudge it threadsafely.
_wake_loop: Optional[asyncio.AbstractEventLoop] = None
_wake_event: Optional[asyncio.Event] = None


def _utcnow() -> datetime:
    return datetime.utcnow()


def register_wake(loop: asyncio.AbstractEventLoop, event: asyncio.Event) -> None:
    global _wake_loop, _wake_event
    _wake_loop, _wake_event = loop, event


def request_wake() -> None:
    """Nudge the delivery loop; harmless no-op when it isn't running."""
    if _wake_loop is not None and _wake_event is not None:
        try:
            _wake_loop.call_soon_threadsafe(_wake_event.set)
        except RuntimeError:
            pass                                  # loop already closed


def sign(secret: str, body: str) -> str:
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def emit(session: Session, tenant_id: int, event_type: str, data: dict) -> int:
    """Queue `event_type` for every subscribed active endpoint of the tenant.

    Adds rows to the caller's session WITHOUT committing — the caller's own
    commit makes document + outbox atomic. Returns the number of deliveries
    queued (0 when no endpoint is subscribed, the overwhelmingly common case,
    which costs one indexed SELECT)."""
    endpoints = session.exec(
        select(WebhookEndpoint).where(
            WebhookEndpoint.tenant_id == tenant_id,
            WebhookEndpoint.is_active == True,  # noqa: E712
        )
    ).all()
    targets = [ep for ep in endpoints if event_type in (ep.events or [])]
    if not targets:
        return 0
    payload_json = json.dumps(
        {"event": event_type, "timestamp": _utcnow().isoformat() + "Z", "data": data},
        default=str,
    )
    now = _utcnow()
    for ep in targets:
        session.add(WebhookDelivery(
            tenant_id=tenant_id, endpoint_id=ep.id, event_type=event_type,
            payload_json=payload_json, status="pending", next_retry=now,
        ))
    request_wake()
    return len(targets)


def _default_post(url: str, body: str, headers: dict) -> tuple[int, str]:
    """Blocking POST; returns (status_code, error_text). error_text is ''
    on a connect success (any HTTP status counts as a response)."""
    try:
        resp = httpx.post(url, content=body, headers=headers, timeout=TIMEOUT_SECONDS)
        return resp.status_code, ""
    except Exception as exc:                       # DNS, refused, timeout, TLS…
        return 0, f"{type(exc).__name__}: {exc}"[:300]


def _apply_result(delivery: WebhookDelivery, status_code: int, error: str) -> None:
    delivery.attempts += 1
    delivery.response_code = status_code or None
    if 200 <= status_code < 300:
        delivery.status = "delivered"
        delivery.delivered_at = _utcnow()
        delivery.last_error = None
        delivery.next_retry = None
    else:
        delivery.last_error = error or f"HTTP {status_code}"
        if delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = "failed"
            delivery.next_retry = None
        else:
            delivery.status = "pending"
            delivery.next_retry = _utcnow() + timedelta(
                seconds=RETRY_DELAYS[delivery.attempts - 1]
            )


def drain_once(
    session: Session,
    post: Callable[[str, str, dict], tuple[int, str]] = _default_post,
    limit: int = BATCH_SIZE,
) -> int:
    """Deliver up to `limit` due rows sequentially (10 s timeout each — a
    slow receiver delays the batch, acceptable for v1 volumes; #115 moves
    this onto the task queue). Returns rows processed."""
    now = _utcnow()
    rows = session.exec(
        select(WebhookDelivery, WebhookEndpoint)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)  # type: ignore[arg-type]
        .where(
            WebhookDelivery.status == "pending",
            WebhookDelivery.next_retry <= now,
            WebhookEndpoint.is_active == True,  # noqa: E712
        )
        .order_by(WebhookDelivery.id)
        .limit(limit)
    ).all()
    for delivery, endpoint in rows:
        headers = {
            "Content-Type": "application/json",
            "X-EasyBooks-Event": delivery.event_type,
            "X-EasyBooks-Delivery": str(delivery.id),
            "X-EasyBooks-Signature": sign(endpoint.secret, delivery.payload_json),
        }
        status_code, error = post(endpoint.url, delivery.payload_json, headers)
        _apply_result(delivery, status_code, error)
        session.add(delivery)
    session.commit()
    return len(rows)


def send_test_ping(endpoint: WebhookEndpoint) -> tuple[int, str]:
    """Fire an immediate signed ping (used by POST /api/webhooks/{id}/test).
    Bypasses the outbox on purpose — the caller wants the live response."""
    body = json.dumps({"event": "ping", "timestamp": _utcnow().isoformat() + "Z"})
    headers = {
        "Content-Type": "application/json",
        "X-EasyBooks-Event": "ping",
        "X-EasyBooks-Signature": sign(endpoint.secret, body),
    }
    return _default_post(endpoint.url, body, headers)
