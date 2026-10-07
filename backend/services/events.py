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
import threading
from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx
from sqlalchemy import update
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
# SQLite rejects concurrent writers on a shared StaticPool connection.
_SQLITE_DRAIN_LOCK = threading.Lock()
TIMEOUT_SECONDS = 10.0
# Claim TTL must cover one HTTP timeout; crashed workers release the row after this.
CLAIM_TTL_SECONDS = 120
CLAIM_STATUS = "sending"

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
    # When Redis/ARQ is available, also nudge the worker outbox drain so
    # delivery doesn't wait for the API-process lifespan loop (#115).
    _enqueue_drain_if_queued()
    return len(targets)


def _enqueue_drain_if_queued() -> None:
    """Best-effort fire-and-forget enqueue; never raises into emit()."""
    try:
        from services.queue import redis_configured
        if not redis_configured():
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        async def _go():
            from services.queue import enqueue
            await enqueue("drain_webhook_outbox_task")
        loop.create_task(_go())
    except Exception:
        pass


def _default_post(url: str, body: str, headers: dict) -> tuple[int, str]:
    """Blocking POST; returns (status_code, error_text). error_text is ''
    on a connect success (any HTTP status counts as a response)."""
    from services.ssrf import public_url_error
    blocked = public_url_error(url)
    if blocked:
        return 0, f"SSRF blocked: {blocked}"
    try:
        resp = httpx.post(url, content=body, headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=False)
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


def _due_delivery_query(now: datetime, limit: int):
    return (
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)  # type: ignore[arg-type]
        .where(
            WebhookDelivery.status.in_(("pending", CLAIM_STATUS)),
            WebhookDelivery.next_retry <= now,
            WebhookEndpoint.is_active == True,  # noqa: E712
        )
        .order_by(WebhookDelivery.id)
        .limit(limit)
    )


def _claim_delivery(session: Session, delivery_id: int, now: datetime) -> bool:
    """Compare-and-set pending/stale-sending → sending. Returns True if we own it."""
    result = session.execute(
        update(WebhookDelivery)
        .where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.status.in_(("pending", CLAIM_STATUS)),
            WebhookDelivery.next_retry <= now,
        )
        .values(
            status=CLAIM_STATUS,
            next_retry=now + timedelta(seconds=CLAIM_TTL_SECONDS),
        )
    )
    return (result.rowcount or 0) == 1


def drain_once(
    session: Session,
    post: Callable[[str, str, dict], tuple[int, str]] = _default_post,
    limit: int = BATCH_SIZE,
) -> int:
    """Deliver up to `limit` due rows. Claims each row before POST so two
    workers cannot send the same delivery (#425). Postgres uses
    ``FOR UPDATE SKIP LOCKED``; SQLite uses the same compare-and-set claim.
    Delivery stays at-least-once (stale claims retry after CLAIM_TTL)."""
    try:
        dialect = session.get_bind().dialect.name
    except Exception:
        dialect = ""
    lock = _SQLITE_DRAIN_LOCK if dialect == "sqlite" else nullcontext()
    with lock:
        return _drain_once_locked(session, post, limit, dialect)


def _drain_once_locked(session, post, limit, dialect) -> int:
    now = _utcnow()
    stmt = _due_delivery_query(now, limit)
    if dialect == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True, of=WebhookDelivery)
    candidates = list(session.exec(stmt).all())
    claimed_ids: list[int] = []
    for row in candidates:
        if row.id is None:
            continue
        if _claim_delivery(session, row.id, now):
            claimed_ids.append(row.id)
    session.commit()

    processed = 0
    for delivery_id in claimed_ids:
        delivery = session.get(WebhookDelivery, delivery_id)
        if not delivery:
            continue
        endpoint = session.get(WebhookEndpoint, delivery.endpoint_id)
        if not endpoint or not endpoint.is_active:
            continue
        headers = {
            "Content-Type": "application/json",
            "X-EasyBooks-Event": delivery.event_type,
            "X-EasyBooks-Delivery": str(delivery.id),
            "X-EasyBooks-Signature": sign(endpoint.secret, delivery.payload_json),
        }
        try:
            from services.ssrf import public_url_error
            blocked = public_url_error(endpoint.url)
            if blocked:
                status_code, error = 0, f"SSRF blocked: {blocked}"
            else:
                status_code, error = post(endpoint.url, delivery.payload_json, headers)
        except Exception as exc:
            status_code, error = 0, f"{type(exc).__name__}: {exc}"[:300]
        _apply_result(delivery, status_code, error)
        session.add(delivery)
        session.commit()
        processed += 1
    return processed


def send_test_ping(endpoint: WebhookEndpoint) -> tuple[int, str]:
    """Fire an immediate signed ping (used by POST /api/webhooks/{id}/test).
    Bypasses the outbox on purpose — the caller wants the live response."""
    from services.ssrf import public_url_error
    blocked = public_url_error(endpoint.url)
    if blocked:
        return 0, f"SSRF blocked: {blocked}"
    body = json.dumps({"event": "ping", "timestamp": _utcnow().isoformat() + "Z"})
    headers = {
        "Content-Type": "application/json",
        "X-EasyBooks-Event": "ping",
        "X-EasyBooks-Signature": sign(endpoint.secret, body),
    }
    return _default_post(endpoint.url, body, headers)


def replay_delivery(
    session: Session, *, tenant_id: int, delivery_id: int,
) -> WebhookDelivery:
    """Clone a delivery into a fresh pending outbox row (#271).

    Keeps the original row as an audit trail; the new row re-enters the
    normal retry ladder from attempts=0.
    """
    src = session.get(WebhookDelivery, delivery_id)
    if not src or src.tenant_id != tenant_id:
        raise ValueError("Delivery not found")
    ep = session.get(WebhookEndpoint, src.endpoint_id)
    if not ep or ep.tenant_id != tenant_id:
        raise ValueError("Endpoint not found")
    now = _utcnow()
    clone = WebhookDelivery(
        tenant_id=tenant_id,
        endpoint_id=src.endpoint_id,
        event_type=src.event_type,
        payload_json=src.payload_json,
        status="pending",
        attempts=0,
        next_retry=now,
        response_code=None,
        last_error=None,
    )
    session.add(clone)
    session.flush()
    request_wake()
    _enqueue_drain_if_queued()
    return clone
