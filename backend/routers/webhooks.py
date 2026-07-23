"""Outgoing webhook endpoints — CRUD + test ping + delivery log (#114).

Secrets are server-generated and returned in FULL exactly once (the create
response); every read endpoint masks to the last 4 chars, same policy as
the AI provider keys (`mask_key`)."""
from __future__ import annotations

import secrets as _secrets
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import WebhookDelivery, WebhookEndpoint
from services.events import EVENT_TYPES, send_test_ping
from services.permissions import perm_dep

from .common import CurrentUserDep, SessionDep, log_audit

router = APIRouter(
    prefix="/api/webhooks",
    tags=["webhooks"],
    dependencies=[perm_dep("webhooks")],
)


class EndpointCreate(BaseModel):
    url: str
    events: list[str]
    description: Optional[str] = None


class EndpointUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[list[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def _mask(secret: str) -> str:
    return "••••" + secret[-4:]


def _validate(body_url: Optional[str], body_events: Optional[list[str]]) -> None:
    if body_url is not None and not (
        body_url.startswith("http://") or body_url.startswith("https://")
    ):
        raise HTTPException(400, "url must start with http:// or https://")
    if body_events is not None:
        unknown = sorted(set(body_events) - set(EVENT_TYPES))
        if unknown:
            raise HTTPException(400, f"Unknown event type(s): {', '.join(unknown)}")


def _get_endpoint(session, user, endpoint_id: int) -> WebhookEndpoint:
    ep = session.get(WebhookEndpoint, endpoint_id)
    if not ep or ep.tenant_id != user.tenant_id:
        raise HTTPException(404, "Webhook endpoint not found")
    return ep


def _serialize(ep: WebhookEndpoint) -> dict:
    return {
        "id": ep.id, "url": ep.url, "events": ep.events or [],
        "description": ep.description, "is_active": ep.is_active,
        "secret_masked": _mask(ep.secret), "created_at": ep.created_at,
    }


@router.get("/event-types")
def list_event_types():
    """The subscribable event vocabulary — drives the UI checkboxes."""
    return EVENT_TYPES


@router.get("")
def list_endpoints(session: SessionDep, user: CurrentUserDep):
    eps = session.exec(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.tenant_id == user.tenant_id)
        .order_by(WebhookEndpoint.id)
    ).all()
    return [_serialize(ep) for ep in eps]


@router.post("", status_code=201, dependencies=[perm_dep("webhooks", "edit")])
def create_endpoint(body: EndpointCreate, session: SessionDep, user: CurrentUserDep):
    _validate(body.url, body.events)
    ep = WebhookEndpoint(
        tenant_id=user.tenant_id, url=body.url, events=body.events,
        description=body.description, secret=_secrets.token_hex(24),
    )
    session.add(ep)
    session.commit()
    session.refresh(ep)
    log_audit(session, user, "CREATE", "webhook_endpoint", ep.id, {"url": ep.url})
    session.commit()
    # The ONLY response that carries the full secret — receivers need it to
    # verify X-EasyBooks-Signature; we never return it again.
    return {**_serialize(ep), "secret": ep.secret}


@router.put("/{endpoint_id}", dependencies=[perm_dep("webhooks", "edit")])
def update_endpoint(
    endpoint_id: int, body: EndpointUpdate, session: SessionDep, user: CurrentUserDep
):
    ep = _get_endpoint(session, user, endpoint_id)
    _validate(body.url, body.events)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    session.add(ep)
    log_audit(session, user, "UPDATE", "webhook_endpoint", ep.id, {"url": ep.url})
    session.commit()
    session.refresh(ep)
    return _serialize(ep)


@router.delete("/{endpoint_id}", status_code=204, dependencies=[perm_dep("webhooks", "edit")])
def delete_endpoint(endpoint_id: int, session: SessionDep, user: CurrentUserDep):
    ep = _get_endpoint(session, user, endpoint_id)
    log_audit(session, user, "DELETE", "webhook_endpoint", ep.id, {"url": ep.url})
    session.delete(ep)                 # deliveries cascade via endpoint_id FK
    session.commit()


@router.post("/{endpoint_id}/test", dependencies=[perm_dep("webhooks", "edit")])
def test_endpoint(endpoint_id: int, session: SessionDep, user: CurrentUserDep):
    """Send a signed `ping` immediately (not via the outbox) and report the
    live response so the user can debug their receiver from the UI."""
    ep = _get_endpoint(session, user, endpoint_id)
    status_code, error = send_test_ping(ep)
    return {
        "ok": 200 <= status_code < 300,
        "response_code": status_code or None,
        "error": error or None,
    }


@router.get("/{endpoint_id}/logs")
def delivery_logs(
    endpoint_id: int, session: SessionDep, user: CurrentUserDep, limit: int = 100
):
    ep = _get_endpoint(session, user, endpoint_id)
    rows = session.exec(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == ep.id)
        .order_by(WebhookDelivery.id.desc())  # type: ignore[attr-defined]
        .limit(min(limit, 100))
    ).all()
    return [
        {
            "id": d.id, "event_type": d.event_type, "status": d.status,
            "attempts": d.attempts, "response_code": d.response_code,
            "last_error": d.last_error, "created_at": d.created_at,
            "delivered_at": d.delivered_at, "next_retry": d.next_retry,
        }
        for d in rows
    ]
