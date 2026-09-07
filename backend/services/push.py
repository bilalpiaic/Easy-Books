"""Push notification hook for the Capacitor shell (#307).

Fans out overdue / approval alerts to registered device tokens. Delivery is
best-effort and never raises into the in-app alert path.

Without FCM_SERVER_KEY / PUSH_WEBHOOK_URL the hook still runs (tokens are
looked up) and returns ``skipped_no_provider`` — CI scaffolding, not a live
APNs/FCM contract. Set FCM_SERVER_KEY (legacy FCM HTTP) or PUSH_WEBHOOK_URL
(JSON POST) when you are ready to send.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from sqlmodel import Session, select

from models import DeviceToken

PUSH_KINDS = frozenset({"overdue_invoice", "approval_needed"})
FCM_ENDPOINT = "https://fcm.googleapis.com/fcm/send"


def _active_tokens(session: Session, *, tenant_id: int, user_id: int) -> list[DeviceToken]:
    return list(
        session.exec(
            select(DeviceToken).where(
                DeviceToken.tenant_id == tenant_id,
                DeviceToken.user_id == user_id,
                DeviceToken.is_active == True,  # noqa: E712
            )
        ).all()
    )


def deliver_one(
    *,
    token: str,
    platform: str,
    title: str,
    body: str,
    data: dict[str, Any],
) -> str:
    """Send one notification. Returns sent | skipped_no_provider | error."""
    webhook = (os.environ.get("PUSH_WEBHOOK_URL") or "").strip()
    fcm_key = (os.environ.get("FCM_SERVER_KEY") or "").strip()
    payload = {
        "token": token,
        "platform": platform,
        "title": title,
        "body": body,
        "data": data,
    }
    if webhook:
        return _post_json(webhook, payload, headers={"Content-Type": "application/json"})
    if fcm_key:
        fcm_body = {
            "to": token,
            "notification": {"title": title, "body": body},
            "data": {k: str(v) for k, v in data.items() if v is not None},
        }
        return _post_json(
            FCM_ENDPOINT,
            fcm_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"key={fcm_key}",
            },
        )
    return "skipped_no_provider"


def _post_json(url: str, body: dict, headers: dict[str, str]) -> str:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if 200 <= getattr(resp, "status", 200) < 300:
                return "sent"
            return "error"
    except urllib.error.HTTPError as exc:
        print(f"[push] HTTP {exc.code} posting to {url}: {exc.reason}")
        return "error"
    except Exception as exc:
        print(f"[push] deliver failed: {exc}")
        return "error"


def fanout_push(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    kind: str,
    title: str,
    body: str,
    href: str | None = None,
) -> list[str]:
    """Look up the user's devices and attempt delivery. Returns per-token statuses."""
    if kind not in PUSH_KINDS:
        return []
    statuses: list[str] = []
    data = {"kind": kind, "href": href or "/alerts"}
    for row in _active_tokens(session, tenant_id=tenant_id, user_id=user_id):
        statuses.append(
            deliver_one(
                token=row.token,
                platform=row.platform,
                title=title,
                body=body,
                data=data,
            )
        )
    return statuses
