"""Agent suggestions, automations, OCR stub, forecasts (#122–#125)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select

from models import AgentAutomation, AgentSuggestion, Invoice, Product
from services import forecasting
from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/suggestions")
def list_suggestions(session: SessionDep, user: CurrentUserDep):
    now = datetime.utcnow()
    rows = session.exec(
        select(AgentSuggestion).where(
            AgentSuggestion.tenant_id == user.tenant_id,
            AgentSuggestion.dismissed == False,  # noqa: E712
        ).order_by(AgentSuggestion.id.desc())  # type: ignore
    ).all()
    return [
        r.model_dump()
        for r in rows
        if not r.expires_at or r.expires_at > now
    ]


@router.post("/suggestions/{sid}/dismiss")
def dismiss_suggestion(sid: int, session: SessionDep, user: CurrentUserDep):
    row = session.get(AgentSuggestion, sid)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404)
    row.dismissed = True
    session.add(row)
    session.commit()
    return {"ok": True}


class AutomationIn(BaseModel):
    name: str
    trigger: str
    agent_prompt: str = ""
    is_active: bool = True
    dry_run_only: bool = True


@router.get("/automations")
def list_automations(session: SessionDep, user: CurrentUserDep):
    return [
        a.model_dump()
        for a in session.exec(
            select(AgentAutomation).where(AgentAutomation.tenant_id == user.tenant_id)
        ).all()
    ]


@router.post("/automations", status_code=201)
def create_automation(body: AutomationIn, session: SessionDep, user: WriteUserDep):
    row = AgentAutomation(tenant_id=user.tenant_id, **body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.model_dump()


@router.post("/automations/{aid}/run")
def run_automation(aid: int, session: SessionDep, user: WriteUserDep, dry_run: bool = True):
    row = session.get(AgentAutomation, aid)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404)
    plan = {
        "automation_id": row.id,
        "name": row.name,
        "trigger": row.trigger,
        "prompt": row.agent_prompt,
        "would_execute": not (dry_run or row.dry_run_only),
        "actions": [
            {"type": "preview", "detail": f"Dry-run of '{row.name}' — no GL writes"},
        ],
    }
    if not (dry_run or row.dry_run_only):
        row.last_run = datetime.utcnow()
        session.add(row)
        session.commit()
    return plan


@router.get("/forecast/revenue")
def forecast_revenue(session: SessionDep, user: CurrentUserDep, periods: int = 90):
    return forecasting.forecast_revenue(session, user.tenant_id, periods)


@router.get("/forecast/cash-flow")
def forecast_cash(session: SessionDep, user: CurrentUserDep, horizon: int = 60, floor: float = 0):
    return forecasting.predict_cash_flow(session, user.tenant_id, horizon, floor)


@router.get("/forecast/customer-risk")
def forecast_churn(session: SessionDep, user: CurrentUserDep):
    return forecasting.score_customer_churn(session, user.tenant_id)


@router.get("/forecast/budget-variance")
def forecast_budget(session: SessionDep, user: CurrentUserDep):
    return forecasting.budget_variance_projection(session, user.tenant_id)


@router.post("/ocr")
async def ocr_invoice(
    session: SessionDep,
    user: WriteUserDep,
    file: UploadFile = File(...),
):
    """Vision OCR → suggested invoice lines (#122). Requires a cloud LLM key."""
    from services.ai_providers import configured_providers, resolve_api_key
    providers = configured_providers(session, user.tenant_id)
    if not providers:
        raise HTTPException(503, "No AI provider configured for OCR")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 8MB)")
    try:
        import base64
        import litellm
        b64 = base64.b64encode(data).decode()
        mime = file.content_type or "image/jpeg"
        prov = providers[0]
        model = (prov.get("models") or ["openai/gpt-4o-mini"])[0]
        provider_key = prov["provider"]
        api_key = resolve_api_key(session, user.tenant_id, provider_key)
        resp = await litellm.acompletion(
            model=model,
            api_key=api_key,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract invoice line items as JSON array of {description, qty, rate}. Return ONLY JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
            max_tokens=1000,
            temperature=0,
        )
        text = resp.choices[0].message.content or "[]"
        start, end = text.find("["), text.rfind("]")
        lines = json.loads(text[start:end + 1] if start >= 0 else "[]")
        return {"ok": True, "lines": lines, "raw": text[:500]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"OCR failed: {type(exc).__name__}: {exc}") from exc
