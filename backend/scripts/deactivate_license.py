"""Remove the signed license from this standalone install.

Deletes ``.easy-books-license`` in the books data dir (``$EB_DATA_DIR``, else
portable ``<repo>/data``, else ``~/.easy-books`` — never ``backend/``).
Source folder, books, and the install ID are not deleted.

Field tools:

    docs\\Deactivate_License.bat     (Windows)
    bash docs/Deactivate_License.sh  (macOS / Linux)

CLI:

    cd backend
    PYTHONPATH=. uv run python -m scripts.deactivate_license

Type ``DEACTIVATE`` when asked, or pass ``--yes``. Restart Easy-Books
afterwards. If the 15-day trial has already ended, the copy locks again
until a new token is pasted.
"""
from __future__ import annotations

import argparse
import os
import sys

CONFIRM = "DEACTIVATE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove the signed Easy-Books install license from this PC.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the DEACTIVATE confirmation (scripts / tests).",
    )
    args = parser.parse_args(argv)

    if not args.yes:
        try:
            typed = input(f"Type {CONFIRM} to remove the license on this PC: ")
        except (EOFError, KeyboardInterrupt):
            typed = ""
        if typed.strip() != CONFIRM:
            print("Not deactivated (confirmation did not match DEACTIVATE).", file=sys.stderr)
            return 1

    os.environ.setdefault("EB_STANDALONE", "true")
    os.environ.setdefault("APP_ENV", "local")
    os.environ.pop("EB_SKIP_DEMO_TRIAL", None)

    from services.standalone_license import deactivate_license, license_path
    from services.standalone_trial import books_data_dir

    os.environ["EB_DATA_DIR"] = str(books_data_dir())
    info = deactivate_license()
    print("License deactivated.", flush=True)
    print(f"  License file: {license_path()} (removed={info.get('removed')})", flush=True)
    print(f"  Licensed now: {info.get('licensed')}", flush=True)
    print("Restart Easy-Books. If the trial has ended this copy will lock.", flush=True)
    print("Books and source are not deleted.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
