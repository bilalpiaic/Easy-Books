"""User-level dynamic report builder API."""
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from routers.common import CurrentUserDep, SessionDep
from services.report_engine import ReportConfig, ReportError, run_report
from services.report_sources import REGISTRY

router = APIRouter(prefix="/api/report-builder", tags=["report-builder"])


@router.get("/sources")
def list_sources(user: CurrentUserDep):
    out = []
    for s in REGISTRY.values():
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
