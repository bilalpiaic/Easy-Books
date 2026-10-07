"""Desktop SQLite / backup-zip tenant import (#430).

Copies one mill tenant's rows onto an existing SaaS tenant. Users are never
copied (email is globally unique); user FKs remap onto the dest owner (or
the ops actor). Healthcare tables are refused when ``DISABLED_MODULES``
includes ``healthcare``. Dry-run uses a savepoint so nothing lands.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import insert, text
from sqlmodel import Session, SQLModel, select

from models import Tenant, User
from services.disabled_modules import is_module_disabled

SKIP_TABLES = {
    "user",
    "userinvite",
    "loginattempt",
    "passwordresetattempt",
    "passwordresettoken",
    "revokedtoken",
    "tenantmembership",
    "apikey",
    "aichatsession",
    "aichatmessage",
    "alembic_version",
    "tenant",
    "auditlog",
}

NATURAL_KEYS = {
    "account": ("code",),
    "settings": ("key",),
    "sequencecounter": ("name",),
}


def _is_healthcare_table(name: str) -> bool:
    return name.lower().startswith("hc_")


def extract_sqlite_path(upload_path: Path) -> Path:
    """Return a filesystem path to ``database.db`` (raw sqlite or zip)."""
    if zipfile.is_zipfile(upload_path):
        with zipfile.ZipFile(upload_path) as zf:
            names = zf.namelist()
            db_name = next(
                (n for n in names if n.endswith("database.db") or n == "database.db"),
                None,
            )
            if not db_name:
                raise HTTPException(400, "Archive is missing database.db")
            tmp = Path(tempfile.mkdtemp(prefix="eb-import-")) / "database.db"
            tmp.write_bytes(zf.read(db_name))
            return tmp
    return upload_path


def _trial_balance(conn: sqlite3.Connection, tenant_id: int) -> dict[str, float]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='journalentry'"
    )
    if not cur.fetchone():
        return {"debit": 0.0, "credit": 0.0}
    row = conn.execute(
        "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) "
        "FROM journalentry WHERE tenant_id = ?",
        (tenant_id,),
    ).fetchone()
    return {"debit": float(row[0] or 0), "credit": float(row[1] or 0)}


def _invoice_count(conn: sqlite3.Connection, tenant_id: int) -> int:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='invoice'"
    )
    if not cur.fetchone():
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM invoice WHERE tenant_id = ?", (tenant_id,)
    ).fetchone()
    return int(row[0] or 0)


def _dest_tb_and_invoices(session: Session, tenant_id: int) -> tuple[dict[str, float], int]:
    inv_n = int(
        session.execute(
            text("SELECT COUNT(*) FROM invoice WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).scalar()
        or 0
    )
    row = session.execute(
        text(
            "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) "
            "FROM journalentry WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    ).fetchone()
    tb = (
        {"debit": float(row[0] or 0), "credit": float(row[1] or 0)}
        if row
        else {"debit": 0.0, "credit": 0.0}
    )
    return tb, inv_n


def _source_tenant_id(conn: sqlite3.Connection, requested: int | None) -> int:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tenant'")
    if not cur.fetchone():
        raise HTTPException(400, "Source database has no tenant table")
    ids = [int(r[0]) for r in conn.execute("SELECT id FROM tenant").fetchall()]
    if not ids:
        raise HTTPException(400, "Source database has no tenants")
    if requested is not None:
        if requested not in ids:
            raise HTTPException(400, f"Source tenant {requested} not found")
        return requested
    if len(ids) > 1:
        raise HTTPException(
            400,
            f"Source has {len(ids)} tenants; pass source_tenant_id",
        )
    return ids[0]


def _hc_row_count(conn: sqlite3.Connection, tenant_id: int) -> int:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'hc_%'"
        ).fetchall()
    ]
    total = 0
    for name in tables:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()}
        if "tenant_id" not in cols:
            continue
        row = conn.execute(
            f"SELECT COUNT(*) FROM {name} WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
        total += int(row[0] or 0)
    return total


def _user_fk_columns(table) -> set[str]:
    out: set[str] = set()
    for fk in table.foreign_keys:
        if fk.column.table.name == "user":
            out.add(fk.parent.name)
    return out


def _id_pk(table) -> Optional[str]:
    pks = [c.name for c in table.primary_key.columns]
    if pks == ["id"]:
        return "id"
    return None


def _almost_equal(a: float, b: float) -> bool:
    return abs(a - b) < 0.005


def import_tenant_from_sqlite(
    session: Session,
    *,
    dest: Tenant,
    sqlite_path: Path,
    source_tenant_id: int | None = None,
    dry_run: bool = True,
    remap_user_id: int | None = None,
) -> dict[str, Any]:
    """Copy one source tenant onto ``dest``. Returns a stats dict."""
    import models  # noqa: F401 — ensure metadata is populated

    path = extract_sqlite_path(Path(sqlite_path))
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        src_tid = _source_tenant_id(src, source_tenant_id)
        src_tb = _trial_balance(src, src_tid)
        src_inv = _invoice_count(src, src_tid)
        hc_n = _hc_row_count(src, src_tid)
        hc_disabled = is_module_disabled("healthcare")
        if hc_disabled and hc_n:
            raise HTTPException(
                400,
                "Source contains healthcare rows but healthcare is disabled on this server",
            )

        owner = session.exec(
            select(User).where(User.tenant_id == dest.id, User.role == "owner")
        ).first()
        user_id = (owner.id if owner else None) or remap_user_id

        source_tables = {
            r[0]
            for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        before_tb, before_inv = _dest_tb_and_invoices(session, dest.id)
        nested = session.begin_nested()
        skipped_users = 0
        try:
            if "user" in source_tables:
                skipped_users = int(
                    src.execute(
                        "SELECT COUNT(*) FROM user WHERE tenant_id = ?", (src_tid,)
                    ).fetchone()[0]
                    or 0
                )
            copied = _copy_rows(
                session,
                src,
                dest_tid=dest.id,
                src_tid=src_tid,
                source_tables=source_tables,
                skip_healthcare=hc_disabled,
                remap_user_id=user_id,
            )
            after_tb, after_inv = _dest_tb_and_invoices(session, dest.id)
            if dry_run:
                nested.rollback()
            else:
                nested.commit()
        except Exception:
            nested.rollback()
            raise

        imported_inv = after_inv - before_inv
        imported_tb = {
            "debit": after_tb["debit"] - before_tb["debit"],
            "credit": after_tb["credit"] - before_tb["credit"],
        }
        return {
            "dry_run": dry_run,
            "source_tenant_id": src_tid,
            "dest_tenant_id": dest.id,
            "source": {"invoice_count": src_inv, "trial_balance": src_tb},
            "imported": {"invoice_count": imported_inv, "trial_balance": imported_tb},
            "invoice_count_match": imported_inv == src_inv,
            "trial_balance_match": (
                _almost_equal(imported_tb["debit"], src_tb["debit"])
                and _almost_equal(imported_tb["credit"], src_tb["credit"])
            ),
            "users_skipped": skipped_users,
            "rows_copied": 0 if dry_run else copied,
            "healthcare_skipped": hc_disabled,
        }
    finally:
        src.close()


def _copy_rows(
    session: Session,
    src: sqlite3.Connection,
    *,
    dest_tid: int,
    src_tid: int,
    source_tables: set[str],
    skip_healthcare: bool,
    remap_user_id: int | None,
) -> int:
    id_maps: dict[str, dict[int, int]] = {}
    copied = 0

    def src_rows(table_name: str, where_sql: str, params: tuple) -> list[sqlite3.Row]:
        if table_name not in source_tables:
            return []
        try:
            return list(src.execute(f"SELECT * FROM {table_name} {where_sql}", params))
        except sqlite3.OperationalError:
            return []

    for table in SQLModel.metadata.sorted_tables:
        name = table.name
        if name in SKIP_TABLES or name not in source_tables:
            continue
        if skip_healthcare and _is_healthcare_table(name):
            continue
        col_names = {c.name for c in table.columns}
        if "tenant_id" not in col_names:
            continue
        rows = src_rows(name, "WHERE tenant_id = ?", (src_tid,))
        copied += _insert_table_rows(
            session, table, rows, dest_tid, id_maps, remap_user_id,
        )

    for table in SQLModel.metadata.sorted_tables:
        name = table.name
        if name in SKIP_TABLES or name not in source_tables:
            continue
        if skip_healthcare and _is_healthcare_table(name):
            continue
        col_names = {c.name for c in table.columns}
        if "tenant_id" in col_names:
            continue
        parent_fk = None
        parent_table = None
        for fk in table.foreign_keys:
            ref = fk.column.table.name
            if ref in id_maps and fk.parent.name in col_names:
                parent_fk = fk.parent.name
                parent_table = ref
                break
        if not parent_fk or not id_maps.get(parent_table):
            continue
        old_ids = list(id_maps[parent_table].keys())
        placeholders = ",".join("?" * len(old_ids))
        rows = src_rows(
            name, f"WHERE {parent_fk} IN ({placeholders})", tuple(old_ids),
        )
        copied += _insert_table_rows(
            session, table, rows, dest_tid, id_maps, remap_user_id,
        )
    return copied


def _insert_table_rows(
    session: Session,
    table,
    rows: list[sqlite3.Row],
    dest_tid: int,
    id_maps: dict[str, dict[int, int]],
    remap_user_id: int | None,
) -> int:
    if not rows:
        return 0
    name = table.name
    col_names = {c.name for c in table.columns}
    user_fks = _user_fk_columns(table)
    pk = _id_pk(table)
    natural = NATURAL_KEYS.get(name)
    dest_by_natural: dict[tuple, int] = {}
    if natural and pk and all(k in col_names for k in natural):
        dest_by_natural = _load_natural_map(session, table, dest_tid, natural, pk)

    fk_targets = [(fk.parent.name, fk.column.table.name) for fk in table.foreign_keys]
    nullable = {c.name: bool(c.nullable) for c in table.columns}

    n = 0
    for raw in rows:
        row = {k: raw[k] for k in raw.keys()}
        old_id = row.get(pk) if pk else None
        payload: dict[str, Any] = {}
        for col in table.columns:
            if col.name not in row:
                continue
            payload[col.name] = _coerce(col, row[col.name])

        if "tenant_id" in col_names:
            payload["tenant_id"] = dest_tid

        for col_name, ref_table in fk_targets:
            if col_name not in payload or payload[col_name] is None:
                continue
            old = payload[col_name]
            if col_name in user_fks or ref_table == "user":
                payload[col_name] = remap_user_id
                continue
            if ref_table == "tenant":
                payload[col_name] = dest_tid
                continue
            mapped = id_maps.get(ref_table, {}).get(int(old))
            if mapped is not None:
                payload[col_name] = mapped
            elif nullable.get(col_name, True):
                payload[col_name] = None

        if natural and pk and old_id is not None:
            key = tuple(payload.get(k) for k in natural)
            existing = dest_by_natural.get(key)
            if existing is not None:
                id_maps.setdefault(name, {})[int(old_id)] = existing
                continue

        if pk:
            payload.pop(pk, None)

        result = session.execute(insert(table).values(**payload))
        if pk and old_id is not None:
            new_id = None
            pk_tuple = result.inserted_primary_key
            if pk_tuple and pk_tuple[0] is not None:
                new_id = int(pk_tuple[0])
            elif result.lastrowid:
                new_id = int(result.lastrowid)
            if new_id is not None:
                id_maps.setdefault(name, {})[int(old_id)] = new_id
        n += 1
    session.flush()
    return n


def _load_natural_map(
    session: Session, table, dest_tid: int, natural: tuple[str, ...], pk: str,
) -> dict[tuple, int]:
    cols = ", ".join([pk, *natural])
    rows = session.execute(
        text(f"SELECT {cols} FROM {table.name} WHERE tenant_id = :tid"),
        {"tid": dest_tid},
    ).fetchall()
    return {tuple(r[1:]): int(r[0]) for r in rows}


def _coerce(col, val: Any) -> Any:
    if val is None:
        return None
    try:
        from sqlalchemy import JSON as SAJSON
        if isinstance(col.type, SAJSON) and isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
    except Exception:
        pass
    return val
