"""FBR Digital Invoicing (PRAL DI API v1.12) endpoints.

POST /api/pra/test                          — validate stub against FBR DI
GET  /api/pra/invoices/{invoice_id}/status  — pra_status + FBR invoiceNumber
POST /api/pra/invoices/{invoice_id}/submit  — validate-then-post retry
GET  /api/pra/logs                          — PRASubmissionLog listing
GET  /api/pra/scenarios                     — SN codes for tenant activity/sector
GET  /api/pra/sale-types                    — FBR saleType list
GET  /api/pra/ref/{kind}                    — reference-data proxy
POST /api/pra/lookup-reg                    — Get_Reg_Type helper
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from models import Invoice, PRASubmissionLog
from routers.common import CurrentUserDep, SessionDep
from services.pra import (
    INVOICE_TYPE_SALE,
    SALE_TYPES,
    fetch_reference,
    get_pra_config,
    local_validate_payload,
    lookup_reg_type,
    parse_di_response,
    scenarios_for,
    submit_to_pra,
)
from services.permissions import perm_dep, apply_own_filter

pra_router = APIRouter(prefix="/pra", tags=["pra"], dependencies=[perm_dep("invoices")])


@pra_router.get("/scenarios")
def list_scenarios(user: CurrentUserDep, session: SessionDep):
    config = get_pra_config(session, user.tenant_id)
    activity = (config or {}).get("business_activity") or "Retailer"
    sector = (config or {}).get("sector") or "Wholesale / Retails"
    return {
        "activity": activity,
        "sector": sector,
        "default": (config or {}).get("default_scenario") or "SN026",
        "items": scenarios_for(activity, sector),
    }


@pra_router.get("/sale-types")
def list_sale_types():
    return [{"id": s, "label": s} for s in SALE_TYPES]


@pra_router.get("/ref/{kind}")
def reference_lookup(
    kind: str,
    user: CurrentUserDep,
    session: SessionDep,
    date: Optional[str] = None,
    transTypeId: Optional[str] = None,
    originationSupplier: Optional[str] = None,
    hs_code: Optional[str] = None,
    annexure_id: Optional[str] = None,
    sro_id: Optional[str] = None,
    rate_id: Optional[str] = None,
    origination_supplier_csv: Optional[str] = None,
):
    config = get_pra_config(session, user.tenant_id) or {}
    params = {k: v for k, v in {
        "date": date,
        "transTypeId": transTypeId,
        "originationSupplier": originationSupplier,
        "hs_code": hs_code,
        "annexure_id": annexure_id,
        "sro_id": sro_id,
        "rate_id": rate_id,
        "origination_supplier_csv": origination_supplier_csv,
    }.items() if v}
    try:
        data = fetch_reference(kind, config.get("token") or "", params)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return data


class RegLookup(BaseModel):
    registration_no: str


@pra_router.post("/lookup-reg")
def lookup_registration(body: RegLookup, user: CurrentUserDep, session: SessionDep):
    config = get_pra_config(session, user.tenant_id) or {}
    return lookup_reg_type(config.get("token") or "", body.registration_no)


@pra_router.post("/test", dependencies=[perm_dep("invoices", "edit")])
def test_pra_connection(user: CurrentUserDep, session: SessionDep):
    """Validate a SN001-shaped stub against FBR DI (does not post)."""
    config = get_pra_config(session, user.tenant_id)
    if not config:
        raise HTTPException(400, "FBR Digital Invoicing is not enabled in Settings.")
    if not config.get("seller_ntn"):
        raise HTTPException(400, "Seller NTN/CNIC (pra_ntn) is required.")

    stub = {
        "invoiceType": INVOICE_TYPE_SALE,
        "invoiceDate": "2025-05-10",
        "sellerNTNCNIC": config["seller_ntn"],
        "sellerBusinessName": config["seller_business_name"],
        "sellerProvince": config["seller_province"],
        "sellerAddress": config["seller_address"],
        "buyerNTNCNIC": "2046004",
        "buyerBusinessName": "Test Buyer",
        "buyerProvince": config["seller_province"],
        "buyerAddress": "Karachi",
        "buyerRegistrationType": "Registered",
        "invoiceRefNo": "",
        "scenarioId": "SN001",
        "items": [{
            "hsCode": "0101.2100",
            "productDescription": "connection test",
            "rate": "18%",
            "uoM": "Numbers, pieces, units",
            "quantity": 1,
            "totalValues": 1180.00,
            "valueSalesExcludingST": 1000.00,
            "fixedNotifiedValueOrRetailPrice": 0.00,
            "salesTaxApplicable": 180.00,
            "salesTaxWithheldAtSource": 0.00,
            "extraTax": 0.00,
            "furtherTax": 0.00,
            "sroScheduleNo": "",
            "fedPayable": 0.00,
            "discount": 0.00,
            "saleType": "Goods at standard rate (default)",
            "sroItemSerialNo": "",
        }],
    }
    local = local_validate_payload(stub, sandbox=True)
    if local:
        return {
            "ok": False,
            "http_status": 0,
            "status_code": "",
            "error": "; ".join(local),
            "sandbox": config["sandbox"],
            "endpoint": config["validate_url"],
        }
    if not config.get("token"):
        return {
            "ok": False,
            "http_status": 0,
            "status_code": "0401",
            "error": "API token is missing. Paste the PRAL Bearer token in Settings.",
            "sandbox": config["sandbox"],
            "endpoint": config["validate_url"],
        }
    try:
        import httpx
        resp = httpx.post(
            config["validate_url"],
            json=stub,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['token']}",
            },
            timeout=15.0,
        )
        try:
            data = resp.json()
        except Exception:
            data = None
        parsed = parse_di_response(data) if data is not None else {
            "ok": False, "status_code": str(resp.status_code), "error": resp.text[:300],
        }
        if resp.status_code == 401:
            parsed = {"ok": False, "status_code": "0401", "error": "Unauthorized — token rejected by FBR"}
        return {
            "ok": parsed.get("ok", False),
            "http_status": resp.status_code,
            "status_code": parsed.get("status_code"),
            "error": parsed.get("error") or "",
            "sandbox": config["sandbox"],
            "endpoint": config["validate_url"],
        }
    except Exception as exc:
        raise HTTPException(502, f"Could not reach FBR DI API: {exc}")


@pra_router.get("/invoices/{invoice_id}/status")
def get_invoice_pra_status(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return {
        "invoice_id": invoice.id,
        "pra_status": invoice.pra_status,
        "pra_fiscal_number": invoice.pra_fiscal_number,
        "pra_usin": invoice.pra_usin,
        "pra_submitted_at": invoice.pra_submitted_at,
        "di_invoice_type": invoice.di_invoice_type,
        "di_scenario_id": invoice.di_scenario_id,
        "error": invoice.pra_response_raw if invoice.pra_status == "failed" else None,
    }


@pra_router.post("/invoices/{invoice_id}/submit", dependencies=[perm_dep("invoices", "edit")])
def retry_pra_submission(invoice_id: int, user: CurrentUserDep, session: SessionDep):
    """Manually (re-)submit an invoice to FBR DI. Safe to retry."""
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not get_pra_config(session, user.tenant_id):
        raise HTTPException(400, "FBR Digital Invoicing is not enabled in Settings.")
    if not invoice.pra_usin:
        invoice.pra_usin = invoice.number
        session.add(invoice)
        session.commit()
    success = submit_to_pra(session, invoice_id)
    session.refresh(invoice)
    return {
        "success": success,
        "pra_status": invoice.pra_status,
        "pra_fiscal_number": invoice.pra_fiscal_number,
        "error": invoice.pra_response_raw if not success else None,
    }


@pra_router.get("/logs")
def list_pra_logs(
    user: CurrentUserDep,
    session: SessionDep,
    invoice_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
):
    inv_q = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    inv_q = apply_own_filter(inv_q, Invoice, user, session)
    allowed_invoice_ids = [r.id for r in session.exec(inv_q).all()]

    q = select(PRASubmissionLog).where(
        PRASubmissionLog.tenant_id == user.tenant_id,
        PRASubmissionLog.invoice_id.in_(allowed_invoice_ids),  # type: ignore[attr-defined]
    )
    if invoice_id:
        q = q.where(PRASubmissionLog.invoice_id == invoice_id)
    q = q.order_by(PRASubmissionLog.attempt_at.desc()).limit(limit)  # type: ignore[attr-defined]
    logs = session.exec(q).all()
    return [
        {
            "id": l.id,
            "invoice_id": l.invoice_id,
            "attempt_at": l.attempt_at,
            "endpoint": l.endpoint,
            "http_status": l.http_status,
            "response_code": l.response_code,
            "success": l.success,
            "error_message": l.error_message,
        }
        for l in logs
    ]
