"""User-level dynamic report builder API."""
import csv
import io
from dataclasses import asdict
from datetime import datetime
import json as _json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select

from models import ReportDefinition
from routers.common import CurrentUserDep, SessionDep
from services.export_utils import safe_cell as _safe_cell
from services.report_engine import MAX_EXPORT_ROWS, ReportConfig, ReportError, run_report
from services.report_sources import REGISTRY, resolve_source
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/report-builder", tags=["report-builder"], dependencies=[perm_dep("report_builder")])


@router.get("/sources")
def list_sources(user: CurrentUserDep, session: SessionDep):
    out = []
    for key in REGISTRY:
        s = resolve_source(session, user.tenant_id, key)
        if s is None:
            continue
        out.append({
            "key": s.key, "label": s.label, "date_field": s.date_field,
            "default_columns": s.default_columns,
            "fields": [{"key": f.key, "label": f.label, "type": f.type.value,
                        "enum_values": f.enum_values, "aggregatable": f.aggregatable,
                        "groupable": f.groupable} for f in s.fields.values()],
        })
    return out


class RunBody(BaseModel):
    source_key: str
    config: ReportConfig
    page: int = 0
    page_size: int = 100


@router.post("/run")
def run(body: RunBody, session: SessionDep, user: CurrentUserDep):
    try:
        res = run_report(session, tenant_id=user.tenant_id, source_key=body.source_key,
                         config=body.config, page=body.page, page_size=min(body.page_size, 500))
    except ReportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "columns": [asdict(c) for c in res.columns],
        "rows": res.rows, "group_by": res.group_by, "footers": res.footers,
        "page": res.page, "page_size": res.page_size, "total_count": res.total_count,
    }


# ---------------------------------------------------------------------------
# Saved-report CRUD
# ---------------------------------------------------------------------------

def _validate_config(source_key: str, config: ReportConfig, session: SessionDep, tenant_id: int):
    from services.report_engine import _AGG_FN, build_predicate, coerce_value
    src = resolve_source(session, tenant_id, source_key)
    if src is None:
        raise HTTPException(400, f"unknown source {source_key!r}")
    try:
        for k in config.columns:
            src.field(k)
        for c in config.filters:
            f = src.field(c.field)
            build_predicate(f, c.op, coerce_value(f.type, c.value))
        for a in config.aggregates:
            if a.fn not in _AGG_FN:
                raise ReportError(f"unknown aggregate function {a.fn!r}")
            if not src.field(a.field).aggregatable:
                raise ReportError(f"{a.field} is not aggregatable")
        for k in config.group_by:
            src.field(k)
    except (KeyError, ReportError) as e:
        raise HTTPException(400, f"invalid config: {e}")


class SaveBody(BaseModel):
    name: str
    source_key: str
    config: ReportConfig
    visibility: str = "private"


def _serialize(rd: ReportDefinition) -> dict:
    return {"id": rd.id, "name": rd.name, "source_key": rd.source_key,
            "visibility": rd.visibility, "owner_id": rd.owner_id,
            "config": _json.loads(rd.config)}


@router.get("/reports")
def list_reports(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(select(ReportDefinition).where(
        ReportDefinition.tenant_id == user.tenant_id)).all()
    visible = [r for r in rows if r.visibility == "shared" or r.owner_id == user.id]
    return [_serialize(r) for r in visible]


@router.get("/reports/{rid}")
def get_report(rid: int, session: SessionDep, user: CurrentUserDep):
    rd = session.get(ReportDefinition, rid)
    if not rd or rd.tenant_id != user.tenant_id or \
       (rd.visibility != "shared" and rd.owner_id != user.id):
        raise HTTPException(404, "not found")
    return _serialize(rd)


@router.post("/reports")
def save_report(body: SaveBody, session: SessionDep, user: CurrentUserDep):
    _validate_config(body.source_key, body.config, session, user.tenant_id)
    rd = ReportDefinition(tenant_id=user.tenant_id, name=body.name, source_key=body.source_key,
                          config=body.config.model_dump_json(), visibility=body.visibility,
                          owner_id=user.id, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    session.add(rd); session.commit(); session.refresh(rd)
    return _serialize(rd)


@router.patch("/reports/{rid}")
def update_report(rid: int, body: SaveBody, session: SessionDep, user: CurrentUserDep):
    rd = session.get(ReportDefinition, rid)
    if not rd or rd.tenant_id != user.tenant_id:
        raise HTTPException(404, "not found")
    if rd.owner_id != user.id:
        raise HTTPException(403, "owner only")
    _validate_config(body.source_key, body.config, session, user.tenant_id)
    rd.name, rd.source_key = body.name, body.source_key
    rd.config, rd.visibility = body.config.model_dump_json(), body.visibility
    rd.updated_at = datetime.utcnow()
    session.add(rd); session.commit(); session.refresh(rd)
    return _serialize(rd)


@router.delete("/reports/{rid}")
def delete_report(rid: int, session: SessionDep, user: CurrentUserDep):
    rd = session.get(ReportDefinition, rid)
    if not rd or rd.tenant_id != user.tenant_id:
        raise HTTPException(404, "not found")
    if rd.owner_id != user.id:
        raise HTTPException(403, "owner only")
    session.delete(rd); session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.post("/export")
def export_report(body: RunBody, session: SessionDep, user: CurrentUserDep,
                  format: str = Query("csv")):
    try:
        res = run_report(session, tenant_id=user.tenant_id, source_key=body.source_key,
                         config=body.config, page=0, page_size=MAX_EXPORT_ROWS)
    except ReportError as e:
        raise HTTPException(400, str(e))
    headers = [c.key for c in res.columns]

    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf); w.writerow(headers)
        for row in res.rows:
            w.writerow([_safe_cell(row.get(h, "")) for h in headers])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={body.source_key}.csv"})

    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.append(headers)
        for row in res.rows:
            ws.append([_safe_cell(row.get(h, "")) for h in headers])
        out = io.BytesIO(); wb.save(out); out.seek(0)
        return StreamingResponse(out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={body.source_key}.xlsx"})

    raise HTTPException(400, f"unknown format {format!r}")
