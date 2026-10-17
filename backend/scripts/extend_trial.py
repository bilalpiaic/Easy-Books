"""Grant another standalone trial window (default 15 days from now).

Field tools (hidden password prompt; the password is not in the scripts):

    docs\\Extend_Trial.bat     (Windows)
    bash docs/Extend_Trial.sh  (macOS / Linux)

From the Easy-Books checkout, after the copy has locked:

    cd backend
    PYTHONPATH=. uv run python -m scripts.extend_trial

The CLI requires the field password (prompt, ``--password``, or
``EB_EXTEND_TRIAL_PASSWORD``). SHA-256 is checked with
``hmac.compare_digest`` against ``DEFAULT_PASSWORD_SHA256`` (override with
``EB_EXTEND_TRIAL_PASSWORD_SHA256``). ``extend_trial()`` in
``services.standalone_trial`` stays passwordless for tests and licensed
automation.

Optional length:

    PYTHONPATH=. uv run python -m scripts.extend_trial --days 15

Then restart the app (``install-and-run`` / desktop). If you passed ``--days``,
export the same value before launch:

    export EB_DEMO_TRIAL_DAYS=15

Data dir matches ``install-and-run``: ``$EB_DATA_DIR``, else portable
``<repo>/data``, else ``~/.easy-books`` (not the ``backend/`` folder).
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import os
import sys

# SHA-256 of the field password. Not the password itself. Override the
# expected digest with EB_EXTEND_TRIAL_PASSWORD_SHA256 if needed.
DEFAULT_PASSWORD_SHA256 = (
    "94e04d02221295eae8011341cdbb792dd1e1b05a3cd27f66839aa6b7f74b140c"
)


def expected_password_sha256() -> str:
    raw = (os.environ.get("EB_EXTEND_TRIAL_PASSWORD_SHA256") or DEFAULT_PASSWORD_SHA256)
    return raw.strip().lower()


def password_matches(plain: str) -> bool:
    digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, expected_password_sha256())


def resolve_standalone_data_dir() -> Path:
    """Books data dir the trial clock is charged against (not ``backend/``)."""
    from services.standalone_trial import books_data_dir

    return books_data_dir()


def _resolve_password(explicit: str | None) -> str | None:
    if explicit is not None:
        return explicit
    env_pw = os.environ.pop("EB_EXTEND_TRIAL_PASSWORD", None)
    if env_pw is not None:
        return env_pw
    try:
        return getpass.getpass("Extend-trial password: ")
    except (EOFError, KeyboardInterrupt):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restart the standalone Easy-Books trial clock from today.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Length of the new window (default: EB_DEMO_TRIAL_DAYS or 15)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Field password (omit to be prompted; or set EB_EXTEND_TRIAL_PASSWORD)",
    )
    args = parser.parse_args(argv)

    password = _resolve_password(args.password)
    if password is None or not password_matches(password):
        print("Incorrect password.", file=sys.stderr)
        return 1

    os.environ.setdefault("EB_STANDALONE", "true")
    os.environ.setdefault("APP_ENV", "local")
    os.environ.pop("EB_SKIP_DEMO_TRIAL", None)
    os.environ["EB_DATA_DIR"] = str(resolve_standalone_data_dir())

    from local_config import data_dir, repo_root
    from services.standalone_trial import (
        INSTALL_EXPIRED_NAME,
        INSTALL_STAMP_NAME,
        expired_marker_path,
        extend_trial,
        stamp_path,
    )

    info = extend_trial(days=args.days)
    print(f"Trial extended {info.get('days')} days from {info.get('started_at')}.", flush=True)
    print(f"  New end:       {info.get('ends_at')}", flush=True)
    print(f"  Data stamp:    {stamp_path()}", flush=True)
    print(f"  Data dir:      {data_dir()}", flush=True)
    print(f"  Expired at:    {expired_marker_path()} (removed)", flush=True)
    print(f"  Folder stamp:  {repo_root() / INSTALL_STAMP_NAME}", flush=True)
    print(f"  Folder latch:  {repo_root() / INSTALL_EXPIRED_NAME} (removed)", flush=True)
    print("Restart Easy-Books for the new window to take effect.", flush=True)
    if args.days is not None:
        print(
            f"Keep this on the process: EB_DEMO_TRIAL_DAYS={args.days}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
