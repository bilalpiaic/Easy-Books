"""Polymorphic document-attachment endpoints.

Attaches PDFs / images / Office docs to any of: invoice, bill, transaction
(manual JV), payment_received, bill_payment, grn, production_order.

Storage layout
--------------
    UPLOAD_ROOT / <tenant_id> / <parent_type> / <parent_id> / <uuid>.<ext>

Tenant isolation is enforced both at the row (`tenant_id` filter on every
query) and at the path (tenant id is the first directory). Files for one
tenant can never be served to another, even on path-traversal attempts —
the resolved real path is asserted to live under that tenant's directory.

Endpoints
---------
- POST   /api/attachments                   multipart upload
- GET    /api/attachments?parent_type=&parent_id=
- GET    /api/attachments/{id}/preview      inline (browser previews PDF/image)
- GET    /api/attachments/{id}/download     attachment Content-Disposition
- DELETE /api/attachments/{id}
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import select

from models import (
    Attachment, Bill, GoodsReceiptNote, Invoice, PaymentReceived,
    BillPayment, ProductionOrder, Transaction,
)
from .common import SessionDep, CurrentUserDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


# ── Config ────────────────────────────────────────────────────────────────────

UPLOAD_ROOT = Path(os.environ.get("UPLOAD_ROOT", "uploads")).resolve()
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))  # 25 MB

# MIME allowlist. We accept the document classes the UI can preview natively
# (PDF, images) plus Office docs (download-only). Executables, scripts, and
# anything else is rejected at upload to keep the storage layer benign.
_ALLOWED_MIME = {
    # Images — previewable
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
    # PDF — previewable in <iframe>
    "application/pdf",
    # Office docs — download-only
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Plain CSV / text
    "text/csv", "text/plain",
}

_PARENT_TABLE = {
    "invoice":           Invoice,
    "bill":              Bill,
    "transaction":       Transaction,
    "payment_received":  PaymentReceived,
    "bill_payment":      BillPayment,
    "grn":               GoodsReceiptNote,
    "production_order":  ProductionOrder,
}


def _ensure_parent_belongs_to_tenant(session, parent_type: str, parent_id: int, tenant_id: int):
    model = _PARENT_TABLE.get(parent_type)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unsupported parent_type '{parent_type}'")
    row = session.exec(
        select(model).where(model.id == parent_id, model.tenant_id == tenant_id)
    ).first()
    if not row:
        # 404 rather than 403 to avoid enumeration across tenants.
        raise HTTPException(status_code=404, detail=f"{parent_type} {parent_id} not found")


def _safe_extension(filename: str) -> str:
    """Return a lowercase extension restricted to [a-z0-9]. Never returns a
    leading dot. Defaults to 'bin' when the input has nothing safe."""
    if not filename or "." not in filename:
        return "bin"
    ext = filename.rsplit(".", 1)[-1].lower()
    safe = "".join(c for c in ext if c.isalnum())[:8]
    return safe or "bin"


def _resolve_storage_path(att: Attachment) -> Path:
    """Resolve the on-disk path for an Attachment row and guarantee it lives
    inside UPLOAD_ROOT/<tenant_id>/. Defends against any future row whose
    file_path was set externally — never trust the row blindly."""
    candidate = (UPLOAD_ROOT / att.file_path).resolve()
    tenant_root = (UPLOAD_ROOT / str(att.tenant_id)).resolve()
    try:
        candidate.relative_to(tenant_root)
    except ValueError:
        raise HTTPException(status_code=500, detail="Attachment path outside tenant root")
    return candidate


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def upload_attachment(
    session: SessionDep,
    user: WriteUserDep,
    parent_type: str = Form(...),
    parent_id: int = Form(...),
    file: UploadFile = File(...),
):
    """Upload one file and bind it to a business record."""
    _ensure_parent_belongs_to_tenant(session, parent_type, parent_id, user.tenant_id)

    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: PDF, images, Office docs, CSV/text.",
        )

    # Stream-read to enforce the size cap without buffering huge uploads in RAM.
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents)} bytes). Limit is {MAX_UPLOAD_BYTES} bytes.",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    ext = _safe_extension(file.filename or "")
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    rel_dir = Path(str(user.tenant_id)) / parent_type / str(parent_id)
    abs_dir = UPLOAD_ROOT / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    rel_path = rel_dir / stored_name
    (UPLOAD_ROOT / rel_path).write_bytes(contents)

    att = Attachment(
        tenant_id=user.tenant_id,
        parent_type=parent_type,
        parent_id=parent_id,
        file_name=stored_name,
        original_name=file.filename or stored_name,
        mime_type=file.content_type,
        size_bytes=len(contents),
        file_path=str(rel_path),
        uploaded_by_id=user.id,
    )
    session.add(att)
    session.flush()
    log_audit(
        session, user, "create", "attachment", att.id,
        {"parent_type": parent_type, "parent_id": parent_id, "name": att.original_name},
    )
    session.commit()
    session.refresh(att)
    return att


@router.get("")
def list_attachments(
    session: SessionDep,
    user: CurrentUserDep,
    parent_type: str,
    parent_id: int,
):
    """List attachments for one parent record. Tenant-scoped."""
    if parent_type not in _PARENT_TABLE:
        raise HTTPException(status_code=400, detail=f"Unsupported parent_type '{parent_type}'")
    rows = session.exec(
        select(Attachment)
        .where(
            Attachment.tenant_id == user.tenant_id,
            Attachment.parent_type == parent_type,
            Attachment.parent_id == parent_id,
        )
        .order_by(Attachment.uploaded_at.desc())
    ).all()
    return rows


@router.get("/{att_id}/preview")
def preview_attachment(att_id: int, session: SessionDep, user: CurrentUserDep):
    """Inline-disposition response — browser previews PDF/image."""
    return _serve(att_id, session, user, disposition="inline")


@router.get("/{att_id}/download")
def download_attachment(att_id: int, session: SessionDep, user: CurrentUserDep):
    """Attachment-disposition response — browser downloads with original name."""
    return _serve(att_id, session, user, disposition="attachment")


@router.delete("/{att_id}", status_code=204)
def delete_attachment(att_id: int, session: SessionDep, user: WriteUserDep):
    att = session.get(Attachment, att_id)
    if not att or att.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    # Best-effort fs cleanup. Row deletion proceeds even if the file is gone —
    # an orphan row is worse than an orphan file.
    try:
        path = _resolve_storage_path(att)
        if path.exists():
            path.unlink()
    except Exception:
        pass
    session.delete(att)
    log_audit(
        session, user, "delete", "attachment", att.id,
        {"parent_type": att.parent_type, "parent_id": att.parent_id, "name": att.original_name},
    )
    session.commit()
    return None


# ── Internal ─────────────────────────────────────────────────────────────────

def _serve(att_id: int, session, user, *, disposition: str):
    att = session.get(Attachment, att_id)
    if not att or att.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = _resolve_storage_path(att)
    if not path.exists():
        raise HTTPException(status_code=410, detail="File missing on disk")
    headers = {
        "Content-Disposition": f'{disposition}; filename="{att.original_name}"',
    }
    return FileResponse(path, media_type=att.mime_type, headers=headers)
