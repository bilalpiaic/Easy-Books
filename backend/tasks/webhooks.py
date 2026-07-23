"""Webhook delivery tasks (#115) — ARQ path alongside the lifespan outbox."""
from __future__ import annotations


async def deliver_webhook_task(ctx, delivery_id: int) -> dict:
    """Deliver a single WebhookDelivery row (retry-aware via events._apply_result)."""
    import db as _db
    from sqlmodel import Session
    from models import WebhookDelivery, WebhookEndpoint
    from services.events import _apply_result, _default_post, sign

    with Session(_db.engine) as session:
        delivery = session.get(WebhookDelivery, delivery_id)
        if not delivery or delivery.status != "pending":
            return {"ok": False, "reason": "not_pending"}
        endpoint = session.get(WebhookEndpoint, delivery.endpoint_id)
        if not endpoint or not endpoint.is_active:
            return {"ok": False, "reason": "endpoint_inactive"}
        headers = {
            "Content-Type": "application/json",
            "X-EasyBooks-Event": delivery.event_type,
            "X-EasyBooks-Delivery": str(delivery.id),
            "X-EasyBooks-Signature": sign(endpoint.secret, delivery.payload_json),
        }
        status_code, error = _default_post(
            endpoint.url, delivery.payload_json, headers
        )
        _apply_result(delivery, status_code, error)
        session.add(delivery)
        session.commit()
        return {
            "ok": True,
            "delivery_id": delivery_id,
            "status": delivery.status,
            "response_code": delivery.response_code,
        }


async def drain_webhook_outbox_task(ctx, limit: int = 25) -> dict:
    """Batch-drain due outbox rows — used by the ARQ cron / worker fallback."""
    import db as _db
    from sqlmodel import Session
    from services.events import drain_once

    with Session(_db.engine) as session:
        n = drain_once(session, limit=limit)
    return {"processed": n}
