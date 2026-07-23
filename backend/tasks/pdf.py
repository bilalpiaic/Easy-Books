"""PDF generation task — WeasyPrint → storage key (#115 / #116)."""
from __future__ import annotations

import json


async def generate_pdf_task(
    ctx,
    template: str,
    data_json: str,
    output_key: str,
    company_name: str = "Easy-Books",
    tagline: str = "",
) -> dict:
    """Render a PDF and store it under `output_key`.

    `data_json` is a JSON string so the payload survives ARQ serialization.
    For `template == "invoice"`, expects `{"invoice": {...}, "lines": [...]}`.
    """
    from services import storage
    from services.pdf import render_invoice_pdf

    data = json.loads(data_json)
    if template != "invoice":
        raise ValueError(f"unsupported pdf template: {template}")
    pdf_bytes = render_invoice_pdf(
        data["invoice"], data.get("lines") or [], company_name, tagline
    )
    url = storage.upload_file(output_key, pdf_bytes, "application/pdf")
    return {"ok": True, "key": output_key, "url": url, "bytes": len(pdf_bytes)}
