"""Activate a signed license on this standalone install.

Writes ``.easy-books-license`` in the books data dir (``$EB_DATA_DIR``, else
portable ``<repo>/data``, else ``~/.easy-books`` — never ``backend/``).

Field tools:

    docs\\Activate_License.bat     (Windows)
    bash docs/Activate_License.sh  (macOS / Linux)

CLI:

    cd backend
    PYTHONPATH=. uv run python -m scripts.activate_license --token EB1....

Or paste the token when prompted. Restart Easy-Books afterwards. Source
folder and books are not deleted. ``EB_SKIP_DEMO_TRIAL=true`` remains a
licensed override that does not need a token.
"""
from __future__ import annotations

import argparse
import os
import sys

from services.standalone_license import (
    LicenseError,
    activate_token,
    existing_user_emails,
    license_path,
    license_status,
)
from services.standalone_trial import books_data_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Activate a signed Easy-Books install license.")
    parser.add_argument(
        "--token",
        default=None,
        help="EB1.… license token (omit to be prompted; or set EB_LICENSE_TOKEN)",
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

    os.environ.setdefault("EB_STANDALONE", "true")
    os.environ.setdefault("APP_ENV", "local")
    os.environ["EB_DATA_DIR"] = str(books_data_dir())

    try:
        info = activate_token(token, emails=existing_user_emails())
    except LicenseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    status = info or license_status()
    print("License activated.", flush=True)
    print(f"  Install id:  {status.get('install_id')}", flush=True)
    print(f"  Email:       {status.get('email')}", flush=True)
    print(f"  Data dir:    {status.get('data_dir')}", flush=True)
    print(f"  License at:  {license_path()}", flush=True)
    if status.get("expires_at"):
        print(f"  Expires:     {status.get('expires_at')}", flush=True)
    print("Restart Easy-Books for the license to take effect.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
