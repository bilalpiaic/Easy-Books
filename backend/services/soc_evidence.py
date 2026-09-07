"""SOC 2–oriented evidence pack (#309).

Assembles a tenant-scoped ZIP of control mappings, user/access listings,
redacted settings, audit samples, and API-key metadata. This is evidence
*assistance* for an auditor — not a certified SOC 2 Type I/II report.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from models import ApiKey, AuditLog, Settings, Tenant, User, UserPermission
from services.export_utils import safe_cell
from services.permissions import PERMISSION_RESOURCES, get_effective_permission

# Trust Services Criteria → product feature → where to collect evidence.
# Periodicity is a suggested collection cadence for the operator, not an SLA.
CONTROLS: tuple[dict[str, str], ...] = (
    {
        "criterion": "CC6.1",
        "title": "Logical access — identification and authentication",
        "product": "JWT session auth, bcrypt password hashing, optional TOTP (#118), API keys (#113)",
        "evidence": "users.csv (totp_enabled), api_keys.csv, Settings → Team",
        "periodicity": "Quarterly access review",
    },
    {
        "criterion": "CC6.2",
        "title": "New user provisioning",
        "product": "Admin-only user create / invite with explicit role (owner/admin/accountant/viewer)",
        "evidence": "users.csv, audit_sample.csv (CREATE user / invite)",
        "periodicity": "On each hire; quarterly review",
    },
    {
        "criterion": "CC6.3",
        "title": "Access modification and removal",
        "product": "Role change, deactivate, API-key revoke (is_active=false)",
        "evidence": "users.csv is_active, api_keys.csv is_active, audit_sample.csv",
        "periodicity": "On termination; quarterly review",
    },
    {
        "criterion": "CC6.6",
        "title": "Encryption in transit",
        "product": "TLS is an operator/platform concern (Caddy / load balancer / Vercel). App issues Bearer JWTs over HTTPS in production.",
        "evidence": "Operator TLS certificate inventory (outside this ZIP)",
        "periodicity": "Annually / on cert rotation",
    },
    {
        "criterion": "CC6.7",
        "title": "Encryption at rest of secrets",
        "product": "Passwords stored as bcrypt hashes; TOTP secrets Fernet-encrypted; cloud API keys write-only in Settings KV",
        "evidence": "settings_snapshot.csv (secrets redacted), users.csv has no password/TOTP material",
        "periodicity": "Annual key-management review",
    },
    {
        "criterion": "CC7.2",
        "title": "System monitoring / audit trail",
        "product": "Tenant-scoped AuditLog on CREATE/UPDATE/DELETE/EXPORT (and related actions)",
        "evidence": "audit_sample.csv (capped sample of recent rows)",
        "periodicity": "Monthly sample; retain per retention policy",
    },
    {
        "criterion": "CC8.1",
        "title": "Change management",
        "product": "Git-based releases; in-app system update (admin) records changelog",
        "evidence": "git history / Settings → Updates (outside this ZIP)",
        "periodicity": "Each production deploy",
    },
    {
        "criterion": "A1.2",
        "title": "Backup and recovery",
        "product": "SQLite on-prem: GET /api/backup/download (admin). Postgres/cloud: platform backups.",
        "evidence": "Backup runbook in runbook.md; this ZIP is not a database backup",
        "periodicity": "Daily backups (operator); quarterly restore test",
    },
    {
        "criterion": "CC6.1-tenant",
        "title": "Multi-tenant isolation",
        "product": "Every accounting table is tenant_id-scoped; JWT carries tenant_id; queries filter by tenant",
        "evidence": "This ZIP contains only the requesting tenant's rows",
        "periodicity": "Annual architecture review / pentest",
    },
    {
        "criterion": "CC6.1-rbac",
        "title": "Role-based and granular access",
        "product": "RBAC roles plus optional User Rights matrix (UserPermission overrides)",
        "evidence": "access_matrix.csv, users.csv role",
        "periodicity": "Quarterly access review",
    },
    {
        "criterion": "C1.1",
        "title": "Confidentiality of configuration secrets",
        "product": "GET /api/settings redacts SECRET_SETTINGS_KEYS (AI keys, CSID, Peppol, MTD/MyInvois secrets)",
        "evidence": "settings_snapshot.csv contains no secret values",
        "periodicity": "Quarterly config snapshot (this pack)",
    },
)

DISCLAIMER = """\
EASY-BOOKS SOC 2 EVIDENCE ASSISTANCE PACK
=========================================

This ZIP is an operator aid. It maps product features to common SOC 2 Trust
Services Criteria and exports tenant-scoped samples (users, access matrix,
redacted settings, recent audit rows).

It is NOT:
- a SOC 2 Type I or Type II report
- an independent auditor's opinion
- a substitute for a CPA firm's examination
- a complete population of all control evidence

An actual SOC 2 engagement is out of scope of this product. Retain this pack
alongside your own policies, HR records, TLS certificates, and backup tests.
"""

RUNBOOK = """\
# Evidence collection runbook

Suggested cadence (adjust to your auditor's PBC list):

| Cadence | What to collect |
| --- | --- |
| Quarterly | Download this evidence pack (Settings → Advanced). Review users.csv for leavers. Spot-check access_matrix.csv. |
| Monthly | Sample audit_sample.csv for unexpected EXPORT / DELETE. |
| On hire / terminate | Confirm Team invite/deactivate and API-key revoke; keep the next quarterly pack. |
| Each production deploy | Record git SHA / Settings → Updates changelog. |
| Annually | Restore test (SQLite backup or cloud snapshot). TLS certificate inventory. Architecture / pentest notes. |

How to export
1. Sign in as owner or admin.
2. Settings → Advanced → Download SOC 2 evidence pack.
3. Store the ZIP in your evidence folder named `soc2-evidence-YYYY-QN.zip`.
4. Do not commit the ZIP to git (it contains user emails and audit samples).

What this pack does not include
- Password hashes, TOTP secrets, raw API keys
- Other tenants' data
- Full general ledger (use Period Close → auditor ZIP for financial close evidence)
"""


def _csv_bytes(headers: list[str], rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for row in rows:
        w.writerow([safe_cell(row.get(h, "")) for h in headers])
    return buf.getvalue().encode("utf-8")


def _iso(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc).isoformat()
        return val.isoformat()
    return str(val)


def controls_catalogue() -> list[dict[str, str]]:
    return [dict(row) for row in CONTROLS]


def build_evidence_pack_zip(session: Session, user: User) -> bytes:
    """Tenant-scoped, formula-injection-safe ZIP. Never includes secret material."""
    tenant = session.get(Tenant, user.tenant_id)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    users = list(session.exec(select(User).where(User.tenant_id == user.tenant_id)).all())
    users_csv = _csv_bytes(
        [
            "id", "email", "full_name", "role", "is_active", "totp_enabled",
            "last_login_at", "created_at", "my_data_only",
        ],
        [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name or "",
                "role": u.role,
                "is_active": u.is_active,
                "totp_enabled": u.totp_enabled,
                "last_login_at": _iso(u.last_login_at),
                "created_at": _iso(u.created_at),
                "my_data_only": u.my_data_only,
            }
            for u in users
        ],
    )

    resource_keys = sorted(PERMISSION_RESOURCES.keys())
    matrix_rows: list[dict] = []
    for u in users:
        for key in resource_keys:
            matrix_rows.append({
                "user_id": u.id,
                "email": u.email,
                "role": u.role,
                "resource_key": key,
                "label": PERMISSION_RESOURCES[key].get("label", key),
                "category": PERMISSION_RESOURCES[key].get("category", ""),
                "access_level": get_effective_permission(u, key, session),
            })
    access_csv = _csv_bytes(
        ["user_id", "email", "role", "resource_key", "label", "category", "access_level"],
        matrix_rows,
    )

    from routers.settings import SECRET_SETTINGS_KEYS

    settings_rows = list(
        session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id)).all()
    )
    snap_rows = []
    for row in settings_rows:
        if row.key in SECRET_SETTINGS_KEYS:
            continue
        snap_rows.append({"key": row.key, "value": row.value})
    settings_csv = _csv_bytes(["key", "value"], snap_rows)

    keys = list(session.exec(select(ApiKey).where(ApiKey.tenant_id == user.tenant_id)).all())
    api_csv = _csv_bytes(
        ["id", "name", "key_hint", "user_id", "is_active", "last_used", "expires_at", "created_at"],
        [
            {
                "id": k.id,
                "name": k.name,
                "key_hint": k.key_hint,
                "user_id": k.user_id,
                "is_active": k.is_active,
                "last_used": _iso(k.last_used),
                "expires_at": _iso(k.expires_at),
                "created_at": _iso(k.created_at),
            }
            for k in keys
        ],
    )

    audits = list(
        session.exec(
            select(AuditLog)
            .where(AuditLog.tenant_id == user.tenant_id)
            .order_by(AuditLog.timestamp.desc())  # type: ignore[attr-defined]
            .limit(500)
        ).all()
    )
    audit_csv = _csv_bytes(
        ["id", "timestamp", "user_id", "action", "entity_type", "entity_id", "detail"],
        [
            {
                "id": a.id,
                "timestamp": _iso(a.timestamp),
                "user_id": a.user_id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id if a.entity_id is not None else "",
                "detail": (a.detail or "")[:500],
            }
            for a in audits
        ],
    )

    try:
        modules = json.loads(tenant.enabled_modules or "[]") if tenant else []
    except Exception:
        modules = []
    modules_csv = _csv_bytes(
        ["module_id"],
        [{"module_id": mid} for mid in modules],
    )

    controls_csv = _csv_bytes(
        ["criterion", "title", "product", "evidence", "periodicity"],
        list(CONTROLS),
    )

    override_rows = list(
        session.exec(
            select(UserPermission).where(UserPermission.tenant_id == user.tenant_id)
        ).all()
    )
    overrides_csv = _csv_bytes(
        ["user_id", "resource_key", "access_level"],
        [
            {
                "user_id": o.user_id,
                "resource_key": o.resource_key,
                "access_level": o.access_level,
            }
            for o in override_rows
        ],
    )

    manifest_csv = _csv_bytes(
        ["file", "description"],
        [
            {"file": "DISCLAIMER.txt", "description": "Not a certified SOC 2 audit"},
            {"file": "runbook.md", "description": "Suggested evidence collection cadence"},
            {"file": "controls.csv", "description": "TSC criterion → product feature map"},
            {"file": "users.csv", "description": "User listing without passwords or TOTP secrets"},
            {"file": "access_matrix.csv", "description": "Effective RBAC + User Rights per resource"},
            {"file": "permission_overrides.csv", "description": "Sparse UserPermission rows (empty if rights unused)"},
            {"file": "settings_snapshot.csv", "description": "Tenant settings with secrets omitted"},
            {"file": "api_keys.csv", "description": "API key metadata (hint only, no hashes)"},
            {"file": "audit_sample.csv", "description": "Up to 500 most recent audit log rows"},
            {"file": "modules.csv", "description": "Installed module IDs"},
        ],
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DISCLAIMER.txt", DISCLAIMER)
        zf.writestr("runbook.md", RUNBOOK)
        zf.writestr("manifest.csv", manifest_csv)
        zf.writestr("controls.csv", controls_csv)
        zf.writestr("users.csv", users_csv)
        zf.writestr("access_matrix.csv", access_csv)
        zf.writestr("permission_overrides.csv", overrides_csv)
        zf.writestr("settings_snapshot.csv", settings_csv)
        zf.writestr("api_keys.csv", api_csv)
        zf.writestr("audit_sample.csv", audit_csv)
        zf.writestr("modules.csv", modules_csv)
        meta = (
            f"tenant_id={user.tenant_id}\n"
            f"tenant_name={tenant.name if tenant else ''}\n"
            f"generated_at={generated}\n"
            f"generated_by={user.email}\n"
            f"kind=soc2_evidence_assistance\n"
        )
        zf.writestr("meta.txt", meta)
    return buf.getvalue()
