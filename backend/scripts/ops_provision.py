"""Provision a complimentary tenant + optional mill SQLite import (#430).

Usage::

    cd backend && PYTHONPATH=. uv run python -m scripts.ops_provision \\
        --company "Spinning Mill A" --email mill@example.com --name "Mill Owner" \\
        --plan starter --no-email

    PYTHONPATH=. uv run python -m scripts.ops_provision \\
        --import-db /path/to/database.db --tenant-id 12 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlmodel import Session, select

from db import engine
from models import Tenant, User
from services.ops_provision import apply_complimentary_plan, provision_tenant
from services.tenant_import import import_tenant_from_sqlite


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Easy-Books ops provision (#430)")
    p.add_argument("--company", help="New tenant company name")
    p.add_argument("--email", help="Owner invite email")
    p.add_argument("--name", default="", help="Owner display name")
    p.add_argument("--plan", default="starter")
    p.add_argument("--model", default="simple", dest="business_model")
    p.add_argument("--no-email", action="store_true", help="Skip SMTP; print invite token")
    p.add_argument("--tenant-id", type=int, help="Existing tenant for plan/import")
    p.add_argument("--comp-plan", help="Set complimentary plan on --tenant-id")
    p.add_argument("--reason", default="ops CLI complimentary plan")
    p.add_argument("--import-db", type=Path, help="Mill sqlite or backup zip")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--apply", action="store_true", help="Commit import (disables dry-run)")
    p.add_argument("--source-tenant-id", type=int, default=None)
    args = p.parse_args(argv)

    dry_run = not args.apply
    if args.dry_run and args.apply:
        dry_run = False

    with Session(engine) as session:
        if args.company and args.email:
            result = provision_tenant(
                session,
                company_name=args.company,
                owner_email=args.email,
                owner_name=args.name,
                plan=args.plan,
                business_model=args.business_model,
                no_email=args.no_email,
            )
            print(json.dumps(result, indent=2, default=str))
            return 0

        if args.tenant_id is None:
            p.error("pass --company/--email to provision, or --tenant-id for plan/import")

        tenant = session.get(Tenant, args.tenant_id)
        if not tenant:
            print(f"Tenant {args.tenant_id} not found", file=sys.stderr)
            return 1

        if args.comp_plan:
            apply_complimentary_plan(session, tenant, args.comp_plan)
            print(json.dumps({"id": tenant.id, "plan": tenant.plan, "reason": args.reason}))

        if args.import_db:
            owner = session.exec(
                select(User).where(User.tenant_id == tenant.id, User.role == "owner")
            ).first()
            result = import_tenant_from_sqlite(
                session,
                dest=tenant,
                sqlite_path=args.import_db,
                source_tenant_id=args.source_tenant_id,
                dry_run=dry_run,
                remap_user_id=owner.id if owner else None,
            )
            if not dry_run:
                session.commit()
            print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
