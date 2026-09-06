"""Tenant print-template clones + sandboxed Jinja HTML (#374)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from jinja2 import DictLoader, StrictUndefined, TemplateError, TemplateNotFound
from jinja2.sandbox import SandboxedEnvironment
from sqlmodel import Session, select

from models import PrintTemplate, User
from services.custom_fields import KEY_RE, active_defs

PRINT_ENTITIES = frozenset({"invoice", "bill"})
BUILTIN_KEY = "standard"
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def assert_print_entity(entity: str) -> str:
    if entity not in PRINT_ENTITIES:
        raise HTTPException(400, f"entity must be one of: {', '.join(sorted(PRINT_ENTITIES))}")
    return entity


def builtin_html(entity: str) -> str:
    path = _TEMPLATE_DIR / f"{entity}.html"
    if not path.is_file():
        raise HTTPException(400, f"No built-in template for {entity}")
    return path.read_text(encoding="utf-8")


def _rows(session: Session, tenant_id: int, entity: Optional[str] = None) -> list[PrintTemplate]:
    q = select(PrintTemplate).where(PrintTemplate.tenant_id == tenant_id)
    if entity:
        q = q.where(PrintTemplate.entity == entity)
    return list(session.exec(q.order_by(PrintTemplate.entity, PrintTemplate.id)).all())


def fmt_template(row: PrintTemplate, *, include_html: bool = True) -> dict:
    return {
        "id": row.id,
        "entity": row.entity,
        "key": row.key,
        "label": row.label,
        "html": row.html if include_html else None,
        "is_builtin": False,
        "is_builtin_override": bool(row.is_builtin_override),
        "is_default": bool(row.is_default),
        "source_extension_id": row.source_extension_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def virtual_standard(entity: str, *, is_default: bool) -> dict:
    return {
        "id": None,
        "entity": entity,
        "key": BUILTIN_KEY,
        "label": "Standard",
        "html": None,
        "is_builtin": True,
        "is_builtin_override": False,
        "is_default": is_default,
        "source_extension_id": None,
        "created_at": None,
    }


def list_templates(session: Session, tenant_id: int, entity: Optional[str] = None) -> list[dict]:
    entities = [assert_print_entity(entity)] if entity else sorted(PRINT_ENTITIES)
    rows = _rows(session, tenant_id, entity)
    by_ent: dict[str, list[PrintTemplate]] = {e: [] for e in entities}
    for r in rows:
        by_ent.setdefault(r.entity, []).append(r)
    out: list[dict] = []
    for ent in entities:
        ent_rows = by_ent.get(ent, [])
        has_default = any(r.is_default for r in ent_rows)
        has_standard_row = any(r.key == BUILTIN_KEY for r in ent_rows)
        if not has_standard_row:
            out.append(virtual_standard(ent, is_default=not has_default))
        for r in ent_rows:
            out.append(fmt_template(r))
    return out


def get_owned(session: Session, tenant_id: int, template_id: int) -> PrintTemplate:
    row = session.get(PrintTemplate, template_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(404, "Print template not found")
    return row


def _clear_defaults(session: Session, tenant_id: int, entity: str, *, keep_id: Optional[int] = None) -> None:
    for r in _rows(session, tenant_id, entity):
        if r.is_default and r.id != keep_id:
            r.is_default = False
            session.add(r)


def clone_template(
    session: Session,
    user: User,
    *,
    entity: str,
    key: str,
    label: str,
    from_key: str = BUILTIN_KEY,
    is_default: bool = False,
    source_extension_id: Optional[str] = None,
) -> PrintTemplate:
    entity = assert_print_entity(entity)
    if not KEY_RE.match(key or ""):
        raise HTTPException(400, "Clone key must match x.<lowercase_ident> (e.g. x.mill_packing)")
    if not (label or "").strip():
        raise HTTPException(400, "label is required")
    dup = session.exec(
        select(PrintTemplate).where(
            PrintTemplate.tenant_id == user.tenant_id,
            PrintTemplate.entity == entity,
            PrintTemplate.key == key,
        )
    ).first()
    if dup:
        raise HTTPException(400, f"Print template '{key}' already exists for {entity}")

    html = None
    if from_key == BUILTIN_KEY:
        html = builtin_html(entity)
    else:
        src = session.exec(
            select(PrintTemplate).where(
                PrintTemplate.tenant_id == user.tenant_id,
                PrintTemplate.entity == entity,
                PrintTemplate.key == from_key,
            )
        ).first()
        if not src or not src.html:
            raise HTTPException(400, f"Source template '{from_key}' not found")
        html = src.html

    if is_default:
        _clear_defaults(session, user.tenant_id, entity)

    row = PrintTemplate(
        tenant_id=user.tenant_id,
        entity=entity,
        key=key,
        label=label.strip(),
        html=html,
        is_builtin_override=False,
        is_default=bool(is_default),
        source_extension_id=source_extension_id,
    )
    session.add(row)
    session.flush()
    return row


def update_template(
    session: Session,
    user: User,
    row: PrintTemplate,
    *,
    label: Optional[str] = None,
    html: Optional[str] = None,
    is_default: Optional[bool] = None,
) -> PrintTemplate:
    if label is not None:
        if not label.strip():
            raise HTTPException(400, "label is required")
        row.label = label.strip()
    if html is not None:
        row.html = html
    if is_default is True:
        _clear_defaults(session, user.tenant_id, row.entity, keep_id=row.id)
        row.is_default = True
    elif is_default is False:
        row.is_default = False
    session.add(row)
    session.flush()
    return row


def delete_template(session: Session, user: User, row: PrintTemplate) -> None:
    session.delete(row)
    session.flush()


def set_default(session: Session, tenant_id: int, entity: str, key: str) -> None:
    entity = assert_print_entity(entity)
    if key == BUILTIN_KEY:
        _clear_defaults(session, tenant_id, entity)
        return
    row = session.exec(
        select(PrintTemplate).where(
            PrintTemplate.tenant_id == tenant_id,
            PrintTemplate.entity == entity,
            PrintTemplate.key == key,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Print template not found")
    _clear_defaults(session, tenant_id, entity, keep_id=row.id)
    row.is_default = True
    session.add(row)
    session.flush()


def html_for_pdf(session: Session, tenant_id: int, entity: str) -> Optional[str]:
    """Return clone HTML when a default clone exists; else None (use file)."""
    row = session.exec(
        select(PrintTemplate).where(
            PrintTemplate.tenant_id == tenant_id,
            PrintTemplate.entity == entity,
            PrintTemplate.is_default == True,  # noqa: E712
        )
    ).first()
    if row and row.html:
        return row.html
    return None


def print_fields_for(
    session: Session,
    tenant_id: int,
    entity: str,
    custom_fields: Optional[dict],
) -> list[dict[str, Any]]:
    values = custom_fields or {}
    out: list[dict[str, Any]] = []
    for d in active_defs(session, tenant_id, entity):
        if not d.show_on_print:
            continue
        val = values.get(d.key)
        out.append({"key": d.key, "label": d.label, "value": "" if val is None else val})
    return out


def render_sandboxed_html(html_source: str, context: dict) -> str:
    """Render clone HTML with no filesystem loader and StrictUndefined.

    ``{% include %}`` / ``{% extends %}`` of unknown names raise TemplateNotFound
    (DictLoader only registers this one string).
    """
    env = SandboxedEnvironment(
        loader=DictLoader({"__print__": html_source}),
        autoescape=True,
        undefined=StrictUndefined,
    )
    try:
        return env.get_template("__print__").render(**context)
    except TemplateNotFound:
        raise
    except TemplateError:
        raise
