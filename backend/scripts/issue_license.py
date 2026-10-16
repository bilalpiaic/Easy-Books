"""Staff tool: issue a signed Easy-Books install license.

Run on the **field-staff laptop / office checkout**, not on the client PC.
Field wrappers: ``docs/Issue_License.bat`` / ``bash docs/Issue_License.sh``.
Map: ``docs/LICENSE_ISSUER.md``. Same seed licenses any client; each token
is bound to that client's install ID.

Requires the private seed (never committed):

    export EB_LICENSE_SIGNING_SEED=<64 hex chars>
    cd backend
    PYTHONPATH=. uv run python -m scripts.issue_license \\
        --install-id <uuid from the client's lock screen> \\
        --email owner@customer.test

Optional ``--expires YYYY-MM-DD`` for a time-limited license. Prints the
``EB1.…`` token on stdout. Activate on the customer machine with
``scripts.activate_license`` / ``docs/Activate_License.sh|.bat``, or paste
the token on the trial-ended screen / Settings → License.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from services.standalone_license import LicenseError, issue_token, public_key_from_seed, signing_seed_hex
from services.standalone_trial import _parse_dt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue a signed Easy-Books install license.")
    parser.add_argument("--install-id", default=None, help="Customer .install-id UUID")
    parser.add_argument("--email", default=None, help="Owner email on that install")
    parser.add_argument(
        "--expires",
        default=None,
        help="Optional end date (YYYY-MM-DD or ISO). Omit for a perpetual license.",
    )
    parser.add_argument(
        "--show-pubkey",
        action="store_true",
        help="Print the public key derived from EB_LICENSE_SIGNING_SEED and exit.",
    )
    args = parser.parse_args(argv)

    seed = signing_seed_hex()
    if not seed:
        print("Set EB_LICENSE_SIGNING_SEED (staff only; never commit).", file=sys.stderr)
        return 1

    if args.show_pubkey:
        try:
            print(public_key_from_seed(seed), flush=True)
        except LicenseError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if not args.install_id or not args.email:
        print("Need --install-id and --email (customer UUID + owner email).", file=sys.stderr)
        return 1

    expires_at = None
    if args.expires:
        expires_at = _parse_dt(args.expires.strip())
        if expires_at is None:
            try:
                expires_at = datetime.strptime(args.expires.strip(), "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                print("Could not parse --expires (use YYYY-MM-DD or ISO).", file=sys.stderr)
                return 1

    try:
        token = issue_token(
            install_id=args.install_id,
            email=args.email,
            seed_hex=seed,
            expires_at=expires_at,
        )
    except LicenseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(token, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
