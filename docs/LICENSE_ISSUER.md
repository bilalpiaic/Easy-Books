# Staff license issuer — what moves, from where

The issuer is **Easy-Books staff**, on **staff’s own machine** (or a vendor ops box). It is **not** run on the customer PC. Nothing in the customer source folder or `~/.easy-books` is copied off the premises. The only secret that can sign licenses is `EB_LICENSE_SIGNING_SEED`; it stays on staff and is never committed, never put in USER_GUIDE, and never sent to the customer.

## Pieces and where they live

| Piece | Where it lives | Who holds it | Moves at issue time? |
|---|---|---|---|
| **Private signing seed** (`EB_LICENSE_SIGNING_SEED`, 64 hex chars) | Staff environment only | Easy-Books staff | **No.** Never copied to the customer, git, or field scripts. |
| **Public key** (`LICENSE_PUBKEY_HEX`) | Already inside the shipped app: `backend/services/standalone_license.py` | Every install | **No.** Arrived with the product. The customer copy uses it to verify tokens. |
| **Install ID** (UUID) | Customer books dir: `~/.easy-books/.install-id` (or `$EB_DATA_DIR`) | Customer PC | **Yes — customer → staff.** Copied from the Trial ended screen or Settings → Advanced → Install license. |
| **Owner email** | Customer database (the owner who signed up) | Customer | **Yes — customer → staff.** Must match an owner on that install. |
| **License token** (`EB1.<payload>.<signature>`) | Created on staff stdout; then stored on the customer as `~/.easy-books/.easy-books-license` | Staff creates, customer keeps | **Yes — staff → customer.** This is the only artifact staff sends. |
| Source folder / books / SQLite | Customer PC | Customer | **No.** Not deleted, not copied, not replaced. |

## Direction of travel

```
CUSTOMER PC                                      STAFF MACHINE
────────────                                     ─────────────
Trial ended screen
  Install ID  ──────────────────────────────►    python -m scripts.issue_license
  Owner email ──────────────────────────────►      --install-id <uuid>
                                                   --email owner@customer.test
                                             +  EB_LICENSE_SIGNING_SEED   (stays here)

                                             prints EB1.… token
  lock screen / Settings /                   ◄────────────────────────────
  docs/Activate_License.bat|.sh

writes ~/.easy-books/.easy-books-license
app verifies with public key already in the install
copy unlocks; files stay on this PC
```

## What staff runs (staff checkout, not the customer folder)

Use any Easy-Books **backend** checkout staff already has (after this change is on the branch). Do **not** log into the customer PC to issue. Do **not** set the seed on the customer copy.

```bash
export EB_LICENSE_SIGNING_SEED=<staff seed, 64 hex chars>
cd backend
PYTHONPATH=. uv run python -m scripts.issue_license \
  --install-id <uuid the customer copied> \
  --email <owner email on that install>
```

Stdout is one line: `EB1.…`. Send **that string** to the customer (email, chat). Optional `--expires YYYY-MM-DD` for a time-limited license; omit it for perpetual.

Confirm the seed matches the public key shipped in the app:

```bash
PYTHONPATH=. uv run python -m scripts.issue_license --show-pubkey
# must print 90523f715496512c8959efb045fc0bebbc25e784a8d0131a8ad6b73648f474df
```

## What the customer runs (customer PC only)

They do **not** receive the seed. They paste the `EB1.…` token:

- Trial ended screen → Activate license, or
- Settings → Advanced → Install license, or
- `docs\Activate_License.bat` / `bash docs/Activate_License.sh`

That writes `~/.easy-books/.easy-books-license` (same books dir as `install-and-run`, never `backend/`). Restart is only needed if they used the field script while the app was stopped; a paste on the lock screen reloads in place.

## What must not move

- Private seed → customer PC, git, USER_GUIDE, `docs/Activate_License.*`, `docs/Extend_Trial.*`
- License file / install ID → staff git checkout (those files stay on the customer books dir)
- Customer source folder or database → anywhere (lock and unlock leave them in place)

`EB_SKIP_DEMO_TRIAL=true` on the customer process is a separate licensed override; it does not use the issuer. Extend trial (`docs/Extend_Trial.*`) is a courtesy 15-day clock restart, not a license.
