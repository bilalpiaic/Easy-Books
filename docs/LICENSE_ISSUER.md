# Field staff: generate a license token for any client

The token is created on **the field staff laptop / office PC** — an Easy-Books checkout **staff already have**, with the private signing seed in the environment. It is **not** created inside the client’s Easy-Books folder and **not** written to the client’s `~/.easy-books` until the client (or you, standing at their keyboard) **activates** the token.

One staff seed signs licenses for **every** client. Each token is bound to **that client’s install ID**. A token made for client A will not unlock client B.

## Where you stand

| Place | What you do there |
|---|---|
| **Staff machine** (your laptop, office, ops box) | Generate the `EB1.…` token. Seed stays here. |
| **Client PC** (their locked Easy-Books) | Read **Install ID** + owner email. Later paste the token. Do not put the seed on this PC. |
| **Not used** | Client source folder, `backend/`, copying their books off the machine. |

On a site visit: keep **your** laptop next to their locked screen. Copy the UUID off their screen into your issuer. Paste the printed token back into their “License token” box. You never run the issuer from their `docs\` folder.

## One-time setup on the staff machine

1. Have an Easy-Books checkout that includes `backend/scripts/issue_license.py` (this branch / a release that has it).
2. Set the signing seed **once** on that machine (64 hex chars; not in git, not in USER_GUIDE):

```bash
export EB_LICENSE_SIGNING_SEED=<staff seed>
```

Windows (current session):

```bat
set EB_LICENSE_SIGNING_SEED=<staff seed>
```

Confirm it matches the public key shipped in the product:

```bash
cd backend
PYTHONPATH=. uv run python -m scripts.issue_license --show-pubkey
# must print 90523f715496512c8959efb045fc0bebbc25e784a8d0131a8ad6b73648f474df
```

## For each client (any number of clients)

1. On the **client** lock screen (or Settings → Advanced → Install license) copy:
   - **Install ID** (UUID)
   - **Owner email** (the email they signed up with on that copy)
2. On the **staff** machine, in **staff’s** checkout:

```bat
docs\Issue_License.bat
```

```bash
bash docs/Issue_License.sh
```

Or:

```bash
cd backend
PYTHONPATH=. uv run python -m scripts.issue_license \
  --install-id <that client's UUID> \
  --email <that client's owner email>
```

3. The command prints **one line** `EB1.…`. That string is the license token for **this** client only.
4. Send it to them, or paste it on their lock screen / Settings, or have them run `docs\Activate_License.bat` / `bash docs/Activate_License.sh` **on the client PC**.
5. For the next client, repeat from step 1 with **their** UUID and email. Do not reuse another client’s token.

Optional time limit: add `--expires YYYY-MM-DD` on the Python command. Omit it for a perpetual license.

## What the client’s PC then holds

Activation writes only:

- `~/.easy-books/.install-id` (already there)
- `~/.easy-books/.easy-books-license` (the token, verified with the public key already in the app)

Their source folder and books stay on that PC.

## Pieces (what moves)

| Piece | Where it lives | Moves? |
|---|---|---|
| Private seed `EB_LICENSE_SIGNING_SEED` | Staff environment | **No** — never client PC, git, or field `.bat`/`.sh` files |
| Public key | Already in `backend/services/standalone_license.py` on every install | **No** |
| Install ID | Client `~/.easy-books/.install-id` | Client → staff (copy/paste) |
| Owner email | Client owner account | Client → staff |
| `EB1.…` token | Staff stdout, then client `~/.easy-books/.easy-books-license` | Staff → client (the only artifact you send) |

```
CLIENT PC (locked)                      STAFF LAPTOP (issuer)
──────────────────                      ────────────────────
Install ID  ─────────────────────────►  docs/Issue_License.bat|.sh
Owner email ─────────────────────────►  or python -m scripts.issue_license
                                        + EB_LICENSE_SIGNING_SEED (stays here)

EB1.… token ◄─────────────────────────  printed on staff screen

paste / Activate_License.*
        ▼
~/.easy-books/.easy-books-license
```

`EB_SKIP_DEMO_TRIAL=true` on the client process is a separate override (no token). `docs/Extend_Trial.*` is another 15 days, not a license.
