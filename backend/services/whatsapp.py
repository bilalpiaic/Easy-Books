"""Meta Cloud API WhatsApp sender for lab report notifications (#237).

Tenants configure write-only credentials in Settings. Business-initiated
messages use an approved template with body params:
  {{1}} = order number
  {{2}} = patient portal URL

When Meta is not configured, callers keep the existing wa.me deep-link fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from sqlmodel import Session, select

from models import Settings
from services.ai_providers import mask_key

WA_TOKEN_KEY = "wa_meta_access_token"
WA_PHONE_ID_KEY = "wa_meta_phone_number_id"
WA_TEMPLATE_KEY = "wa_meta_template_name"
WA_LANG_KEY = "wa_meta_template_lang"

WA_SECRET_SETTINGS_KEYS = frozenset({WA_TOKEN_KEY})

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


@dataclass(frozen=True)
class SendResult:
    ok: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


def _setting(session: Session, tenant_id: int, key: str) -> Optional[str]:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row and row.value else None


def is_configured(session: Session, tenant_id: int) -> bool:
    token = _setting(session, tenant_id, WA_TOKEN_KEY)
    phone_id = _setting(session, tenant_id, WA_PHONE_ID_KEY)
    template = _setting(session, tenant_id, WA_TEMPLATE_KEY)
    return bool(token and phone_id and template)


def status_payload(session: Session, tenant_id: int) -> dict:
    token = _setting(session, tenant_id, WA_TOKEN_KEY)
    phone_id = _setting(session, tenant_id, WA_PHONE_ID_KEY)
    template = _setting(session, tenant_id, WA_TEMPLATE_KEY)
    lang = _setting(session, tenant_id, WA_LANG_KEY) or "en"
    return {
        "configured": bool(token and phone_id and template),
        "token_tail": mask_key(token),
        "phone_number_id_set": bool(phone_id),
        "phone_number_id": phone_id or "",
        "template_name": template or "",
        "template_lang": lang,
    }


def send_lab_report_ready(
    session: Session,
    tenant_id: int,
    *,
    to_digits: str,
    order_number: str,
    portal_url: str,
    client: Optional[httpx.Client] = None,
) -> SendResult:
    """Send the lab-report-ready template via Meta Graph API.

    Never raises — returns SendResult with error text on failure so publish
    can keep portal/email success and fall back to wa.me.
    """
    token = _setting(session, tenant_id, WA_TOKEN_KEY)
    phone_id = _setting(session, tenant_id, WA_PHONE_ID_KEY)
    template = _setting(session, tenant_id, WA_TEMPLATE_KEY)
    lang = _setting(session, tenant_id, WA_LANG_KEY) or "en"

    if not (token and phone_id and template):
        return SendResult(ok=False, error="WhatsApp Meta API is not configured")

    digits = "".join(c for c in (to_digits or "") if c.isdigit())
    if not digits:
        return SendResult(ok=False, error="Patient has no phone number for WhatsApp")

    payload = {
        "messaging_product": "whatsapp",
        "to": digits,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": lang},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": order_number},
                        {"type": "text", "text": portal_url},
                    ],
                }
            ],
        },
    }
    url = f"{GRAPH_BASE}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    owns_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        resp = http.post(url, json=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001 — never abort publish
        return SendResult(ok=False, error=str(exc)[:300])
    finally:
        if owns_client:
            http.close()

    if resp.status_code >= 400:
        detail = resp.text[:300]
        try:
            err = resp.json().get("error", {})
            if isinstance(err, dict) and err.get("message"):
                detail = str(err["message"])[:300]
        except Exception:
            pass
        return SendResult(ok=False, error=detail)

    message_id = None
    try:
        data = resp.json()
        msgs = data.get("messages") or []
        if msgs and isinstance(msgs[0], dict):
            message_id = msgs[0].get("id")
    except Exception:
        pass
    return SendResult(ok=True, message_id=message_id)
