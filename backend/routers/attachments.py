"""Polymorphic document-attachment endpoints.

Attaches PDFs / images / Office docs to any of: invoice, bill, transaction
(manual JV), payment_received, bill_payment, grn, production_order.

Files go through ``services.storage`` (#426): local disk or S3/Spaces.
Keys: tenants/{tenant_id}/attachment/{uuid}.{ext}. Supabase remains a
read fallback for rows still pointing at the old bucket layout.

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

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import select

from models import (
    Attachment, Bill, GoodsReceiptNote, Invoice, PaymentReceived,
    BillPayment, ProductionOrder, Transaction,
)
from services.storage import delete_file, download_file, object_key, upload_file
from .common import SessionDep, CurrentUserDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))  # 25 MB

_ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv", "text/plain",
}

_PARENT_TABLE = {
    "invoice":          Invoice,
    "bill":             Bill,
    "transaction":      Transaction,
    "payment_received": PaymentReceived,
    "bill_payment":     BillPayment,
    "grn":              GoodsReceiptNote,
    "production_order": ProductionOrder,
}


def _ensure_parent_belongs_to_tenant(session, parent_type: str, parent_id: int, tenant_id: int):
    model = _PARENT_TABLE.get(parent_type)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unsupported parent_type '{parent_type}'")
    row = session.exec(
        select(model).where(model.id == parent_id, model.tenant_id == tenant_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"{parent_type} {parent_id} not found")


def _safe_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return "bin"
    ext = filename.rsplit(".", 1)[-1].lower()
    safe = "".join(c for c in ext if c.isalnum())[:8]
    return safe or "bin"


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

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents)} bytes). Limit is {MAX_UPLOAD_BYTES} bytes.",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    from services.saas import check_storage_quota
    check_storage_quota(session, user.tenant_id, extra_bytes=len(contents))

    ext = _safe_extension(file.filename or "")
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    path = object_key(user.tenant_id, "attachment", stored_name)

    try:
        upload_file(path, contents, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Storage upload failed: {exc}") from exc

    att = Attachment(
        tenant_id=user.tenant_id,
        parent_type=parent_type,
        parent_id=parent_id,
        file_name=stored_name,
        original_name=file.filename or stored_name,
        mime_type=file.content_type,
        size_bytes=len(contents),
        file_path=path,
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
    try:
        delete_file(att.file_path)
    except Exception:
        pass
    session.delete(att)
    log_audit(
        session, user, "delete", "attachment", att.id,
        {"parent_type": att.parent_type, "parent_id": att.parent_id, "name": att.original_name},
    )
    session.commit()
    return None


def _serve(att_id: int, session, user, *, disposition: str):
    att = session.get(Attachment, att_id)
    if not att or att.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        data = download_file(att.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Attachment file missing") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Storage download failed: {exc}") from exc
    headers = {"Content-Disposition": f'{disposition}; filename="{att.original_name}"'}
    return Response(content=data, media_type=att.mime_type, headers=headers)
