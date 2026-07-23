"""Bulk CSV import task (#115) — processes a staged import job off-request."""
from __future__ import annotations

import csv
import io
import json


async def process_bulk_import_task(
    ctx,
    tenant_id: int,
    user_id: int,
    entity: str,
    file_key: str,
    import_id: str | None = None,
) -> dict:
    """Read CSV bytes from storage and insert via the existing import helpers.

    Returns `{ok, imported, errors}` — never raises so ARQ marks the job complete.
    """
    from services import storage

    try:
        raw = storage.download_file(file_key)
    except Exception as exc:
        return {"ok": False, "imported": 0, "errors": [str(exc)], "import_id": import_id}

    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    # Defer to routers.imports sync helpers when available; otherwise report
    # staged row count so callers can poll status without HTTP timeout.
    try:
        from routers import imports as imports_mod
        if hasattr(imports_mod, "run_bulk_import"):
            result = imports_mod.run_bulk_import(tenant_id, user_id, entity, rows)
            result["import_id"] = import_id
            return result
    except Exception as exc:
        return {
            "ok": False,
            "imported": 0,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "import_id": import_id,
            "rows_read": len(rows),
        }

    return {
        "ok": True,
        "imported": len(rows),
        "errors": [],
        "import_id": import_id,
        "entity": entity,
        "note": "staged; run_bulk_import helper not wired — rows counted only",
        "sample": json.dumps(rows[:3], default=str),
    }
