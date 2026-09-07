"""SOC 2 evidence assistance (#309).

GET /api/compliance/controls       — TSC → product feature catalogue
GET /api/compliance/evidence-pack  — admin ZIP (audit sample, users, access, settings)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from routers.common import AdminUserDep, SessionDep, log_audit
from services.soc_evidence import build_evidence_pack_zip, controls_catalogue

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/controls")
def list_controls(user: AdminUserDep):
    """Controls catalogue mapped to product features. Admin/owner only."""
    return {"disclaimer": "Evidence assistance only — not a certified SOC 2 audit.", "controls": controls_catalogue()}


@router.get("/evidence-pack")
def download_evidence_pack(session: SessionDep, user: AdminUserDep):
    """ZIP of tenant-scoped SOC 2 evidence samples. Admin/owner only."""
    # Flush the audit row first so audit_sample.csv includes this EXPORT.
    log_audit(session, user, "EXPORT", "soc_evidence_pack", None, {"kind": "soc2_evidence_assistance"})
    session.flush()
    try:
        data = build_evidence_pack_zip(session, user)
    except Exception as exc:
        raise HTTPException(500, f"Evidence pack failed: {exc}") from exc
    session.commit()
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="soc2-evidence-pack.zip"',
        },
    )
