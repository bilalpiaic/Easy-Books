"""Authenticated tenant file downloads (#418). Replaces the public /uploads mount."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from routers.common import CurrentUserDep
from services.storage import download_file, sniff_image

router = APIRouter(prefix="/api/files", tags=["files"])

_PDF = b"%PDF"


def _safe_key(path: str, tenant_id: int) -> str:
    key = path.lstrip("/")
    if not key or ".." in key.split("/"):
        raise HTTPException(404, "File not found")
    first = key.split("/", 1)[0]
    if first != str(tenant_id):
        raise HTTPException(404, "File not found")
    return key


def _headers(filename: str, content_type: str, inline: bool) -> dict[str, str]:
    disp = "inline" if inline else "attachment"
    return {
        "Content-Type": content_type,
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'{disp}; filename="{filename}"',
        "Cache-Control": "private, no-store",
    }


@router.get("/{path:path}")
def get_file(path: str, user: CurrentUserDep):
    key = _safe_key(path, user.tenant_id)
    try:
        data = download_file(key)
    except FileNotFoundError:
        raise HTTPException(404, "File not found")
    name = key.rsplit("/", 1)[-1] or "file"
    if data.startswith(_PDF) or name.lower().endswith(".pdf"):
        return Response(
            content=data,
            headers=_headers(name if name.endswith(".pdf") else f"{name}.pdf", "application/pdf", False),
        )
    try:
        _ext, mime = sniff_image(data)
        return Response(content=data, headers=_headers(name, mime, True))
    except ValueError:
        return Response(
            content=data,
            headers=_headers(name, "application/octet-stream", False),
        )
