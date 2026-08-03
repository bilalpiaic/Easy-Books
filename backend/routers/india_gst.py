"""India GST endpoints (#265).

GET  /api/india-gst/gstr1?start=&end=     — GSTR-1 B2B summary JSON
GET  /api/india-gst/gstr3b?start=&end=    — GSTR-3B outward-supply summary
GET  /api/india-gst/gstr1/csv?start=&end= — CSV download
POST /api/india-gst/suggest-tax           — place-of-supply tax split preview
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from routers.common import CurrentUserDep, SessionDep
from services.india_gst import (
    build_gstr1_summary,
    build_gstr3b_summary,
    gstr1_to_csv,
    is_india_gst_enabled,
    module_installed,
    place_of_supply_interstate,
    suggest_tax_split,
)
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/india-gst",
    tags=["india-gst"],
    dependencies=[perm_dep("report.tax")],
)


def _require_module(session, tenant_id: int) -> None:
    if not module_installed(session, tenant_id):
        raise HTTPException(403, "India GST module is not installed")


class SuggestTaxBody(BaseModel):
    seller_state: Optional[str] = None
    buyer_state: Optional[str] = None
    taxable: Decimal = Decimal("0")


@router.get("/gstr1")
def gstr1(
    session: SessionDep,
    user: CurrentUserDep,
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
):
    _require_module(session, user.tenant_id)
    return build_gstr1_summary(session, user.tenant_id, start, end)


@router.get("/gstr3b")
def gstr3b(
    session: SessionDep,
    user: CurrentUserDep,
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
):
    _require_module(session, user.tenant_id)
    return build_gstr3b_summary(session, user.tenant_id, start, end)


@router.get("/gstr1/csv")
def gstr1_csv(
    session: SessionDep,
    user: CurrentUserDep,
    start: str = Query(...),
    end: str = Query(...),
):
    _require_module(session, user.tenant_id)
    summary = build_gstr1_summary(session, user.tenant_id, start, end)
    csv_text = gstr1_to_csv(summary)
    filename = f"gstr1-{start}-{end}.csv"
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/suggest-tax")
def suggest_tax(session: SessionDep, user: CurrentUserDep, body: SuggestTaxBody):
    _require_module(session, user.tenant_id)
    if not is_india_gst_enabled(session, user.tenant_id):
        raise HTTPException(400, "India GST is disabled in Settings")
    legs = suggest_tax_split(
        session,
        user.tenant_id,
        body.seller_state,
        body.buyer_state,
        body.taxable,
    )
    return {
        "interstate": place_of_supply_interstate(body.seller_state, body.buyer_state),
        "legs": legs,
        "total_tax": float(sum(Decimal(str(l["amount"])) for l in legs)),
    }
