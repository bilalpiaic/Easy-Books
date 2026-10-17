"""Activate a signed license on this standalone install.

Writes ``.easy-books-license`` in the books data dir (``$EB_DATA_DIR``, else
portable ``<repo>/data``, else ``~/.easy-books`` — never ``backend/``).

Field tools:

    docs\\Activate_License.bat     (Windows)
    bash docs/Activate_License.sh  (macOS / Linux)

CLI:

    cd backend
    PYTHONPATH=. uv run python -m scripts.activate_license --token EB1.... --plan basic

``--plan`` is required: ``basic`` (Starter), ``pro``, or ``enterprise``. It
must match the plan signed into the token. Or set ``EB_LICENSE_PLAN``.

Or paste the token and pick the category when prompted. Restart Easy-Books
afterwards. Source folder and books are not deleted.
``EB_SKIP_DEMO_TRIAL=true`` remains a licensed override that does not need
a token.
"""
from __future__ import annotations

import argparse
import os
import sys

from services.standalone_license import (
    PLAN_LABELS,
    LicenseError,
    activate_token,
    existing_user_emails,
    license_path,
    license_status,
    canonical_plan,
)
from services.standalone_trial import books_data_dir


_CHOICE_TO_PLAN = {
    "1": "starter",
    "2": "pro",
    "3": "enterprise",
    "basic": "starter",
    "starter": "starter",
    "pro": "pro",
    "enterprise": "enterprise",
}


def _prompt_plan() -> str | None:
    print("Select the client category this license is for:", flush=True)
    print("  1) Basic", flush=True)
    print("  2) Pro", flush=True)
    print("  3) Enterprise", flush=True)
    try:
        raw = input("Category [1/2/3]: ")
    except (EOFError, KeyboardInterrupt):
        return None
    return _CHOICE_TO_PLAN.get((raw or "").strip().lower())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Activate a signed Easy-Books install license.")
    parser.add_argument(
        "--token",
        default=None,
        help="EB1.… license token (omit to be prompted; or set EB_LICENSE_TOKEN)",
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="Client category: basic (Starter), pro, or enterprise (or EB_LICENSE_PLAN)",
    )
    args = parser.parse_args(argv)

    token = args.token
    if token is None:
        token = os.environ.pop("EB_LICENSE_TOKEN", None)
    if token is None:
        try:
            token = input("License token: ")
        except (EOFError, KeyboardInterrupt):
            token = None
    if not (token or "").strip():
        print("A license token is required.", file=sys.stderr)
        return 1

    plan = args.plan or os.environ.get("EB_LICENSE_PLAN")
    if not (plan or "").strip():
        plan = _prompt_plan()
    try:
        plan = canonical_plan(plan, required=True)
    except LicenseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    os.environ.setdefault("EB_STANDALONE", "true")
    os.environ.setdefault("APP_ENV", "local")
    os.environ["EB_DATA_DIR"] = str(books_data_dir())

    try:
        info = activate_token(
            token,
            emails=existing_user_emails(),
            selected_plan=plan,
        )
    except LicenseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    status = info or license_status()
    print("License activated.", flush=True)
    print(f"  Install id:  {status.get('install_id')}", flush=True)
    print(f"  Email:       {status.get('email')}", flush=True)
    print(f"  Data dir:    {status.get('data_dir')}", flush=True)
    print(f"  License at:  {license_path()}", flush=True)
    paid = status.get("plan")
    if paid:
        print(f"  Plan:        {PLAN_LABELS.get(paid, paid)}", flush=True)
    extras = status.get("addons") or []
    if extras:
        print(f"  Add-ons:     {', '.join(extras)}", flush=True)
    if status.get("expires_at"):
        print(f"  Expires:     {status.get('expires_at')}", flush=True)

    try:
        from sqlmodel import Session

        from db import engine
        from services.entitlements import apply_licensed_commercial

        with Session(engine) as session:
            commercial = apply_licensed_commercial(session)
            session.commit()
        if commercial.get("applied"):
            print(
                f"  Applied to tenant {commercial.get('tenant_id')} "
                f"({commercial.get('plan')}).",
                flush=True,
            )
    except Exception as exc:
        print(f"  Plan apply skipped ({type(exc).__name__}: {exc}). Restart Easy-Books.", flush=True)

    print("Restart Easy-Books for the license to take effect.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
