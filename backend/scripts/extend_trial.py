"""Grant another standalone trial window (default 15 days from now).

Usage (from the Easy-Books checkout, after the copy has locked):

    cd backend
    PYTHONPATH=. uv run python -m scripts.extend_trial

Optional length:

    PYTHONPATH=. uv run python -m scripts.extend_trial --days 15

Then restart the app (``install-and-run`` / desktop). If you passed ``--days``,
export the same value before launch:

    export EB_DEMO_TRIAL_DAYS=15

Data dir defaults to ``$EB_DATA_DIR`` or ``~/.easy-books``.
"""
from __future__ import annotations

import argparse
import os
import sys


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
    args = parser.parse_args(argv)
    os.environ.setdefault("EB_STANDALONE", "true")
    os.environ.setdefault("APP_ENV", "local")
    os.environ.pop("EB_SKIP_DEMO_TRIAL", None)

    from local_config import data_dir
    from services.standalone_trial import extend_trial, stamp_path, expired_marker_path

    info = extend_trial(days=args.days)
    print(f"Trial extended {info.get('days')} days from {info.get('started_at')}.", flush=True)
    print(f"  New end:     {info.get('ends_at')}", flush=True)
    print(f"  Data stamp:  {stamp_path()}", flush=True)
    print(f"  Data dir:    {data_dir()}", flush=True)
    print(f"  Expired at:  {expired_marker_path()} (removed)", flush=True)
    print("Restart Easy-Books for the new window to take effect.", flush=True)
    if args.days is not None:
        print(
            f"Keep this on the process: EB_DEMO_TRIAL_DAYS={args.days}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
