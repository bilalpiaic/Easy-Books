"""Force-expire the standalone trial clock (QA / staff).

Field tools:

    docs\\Expire_Trial.bat     (Windows)
    bash docs/Expire_Trial.sh  (macOS / Linux)

CLI:

    cd backend
    PYTHONPATH=. uv run python -m scripts.expire_trial

Type ``EXPIRE`` when asked, or pass ``--yes``. This backdates
``.demo-trial-started`` and writes expired latches in the books data dir
(``$EB_DATA_DIR``, else portable ``<repo>/data``, else ``~/.easy-books`` —
never ``backend/``). Source folder and books are not deleted. A valid
license file still keeps the copy unlocked.

Then refresh the login page (or restart Easy-Books).
"""
from __future__ import annotations

import argparse
import os
import sys


CONFIRM = "EXPIRE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Force-expire the standalone Easy-Books trial clock (lock the copy).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the EXPIRE confirmation (scripts / tests).",
    )
    args = parser.parse_args(argv)

    if not args.yes:
        try:
            typed = input(f'Type {CONFIRM} to force-expire this copy: ')
        except (EOFError, KeyboardInterrupt):
            typed = ""
        if typed.strip() != CONFIRM:
            print("Not expired (confirmation did not match EXPIRE).", file=sys.stderr)
            return 1

    os.environ.setdefault("EB_STANDALONE", "true")
    os.environ.setdefault("APP_ENV", "local")
    os.environ.pop("EB_SKIP_DEMO_TRIAL", None)

    from services.standalone_license import is_licensed, license_path
    from services.standalone_trial import (
        INSTALL_EXPIRED_NAME,
        INSTALL_STAMP_NAME,
        books_data_dir,
        expired_marker_path,
        force_expire_trial,
        stamp_path,
    )
    from local_config import repo_root

    os.environ["EB_DATA_DIR"] = str(books_data_dir())
    info = force_expire_trial()
    print("Trial force-expired.", flush=True)
    print(f"  Started (backdated): {info.get('started_at')}", flush=True)
    print(f"  Ended:               {info.get('ends_at')}", flush=True)
    print(f"  Data stamp:          {stamp_path()}", flush=True)
    print(f"  Expired latch:       {expired_marker_path()}", flush=True)
    print(f"  Folder stamp:        {repo_root() / INSTALL_STAMP_NAME}", flush=True)
    print(f"  Folder latch:        {repo_root() / INSTALL_EXPIRED_NAME}", flush=True)
    if is_licensed():
        print(
            f"  License still valid: {license_path()} — copy stays unlocked until "
            "you remove that file.",
            flush=True,
        )
    else:
        print("  Locked:              yes (no valid license file)", flush=True)
    print("Refresh login or restart Easy-Books to see Trial ended.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
