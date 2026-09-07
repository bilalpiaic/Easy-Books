# SOC 2 evidence pack (assistance, not a certified audit)

Easy-Books can export a **tenant-scoped evidence ZIP** that maps product
features to common SOC 2 Trust Services Criteria and dumps samples an
auditor typically asks for (users, access matrix, redacted settings, audit
log excerpt).

**This is evidence assistance only.** It is not a SOC 2 Type I or Type II
report, not an independent auditor's opinion, and not a substitute for a
CPA firm's examination. Completing a certified SOC 2 engagement is out of
scope of this product.

## How to export

1. Sign in as **owner** or **admin**.
2. Open **Settings → Advanced**.
3. Click **Download SOC 2 evidence pack**.
4. Store the file as `soc2-evidence-YYYY-QN.zip` in your evidence folder.
5. Do **not** commit the ZIP to git (it contains user emails and audit samples).

API (same ZIP): `GET /api/compliance/evidence-pack`  
Catalogue JSON: `GET /api/compliance/controls`  
Both endpoints require admin/owner (`AdminUserDep`). Each download writes an
`EXPORT` / `soc_evidence_pack` audit row.

## Suggested collection cadence

| Cadence | What to collect |
| --- | --- |
| Quarterly | This evidence pack. Review `users.csv` for leavers. Spot-check `access_matrix.csv`. |
| Monthly | Sample `audit_sample.csv` for unexpected `EXPORT` / `DELETE`. |
| On hire / terminate | Confirm Team invite/deactivate and API-key revoke. |
| Each production deploy | Record git SHA / Settings → Updates changelog. |
| Annually | Restore test (SQLite backup or cloud snapshot). TLS inventory. Architecture / pentest notes. |

## What is in the ZIP

| File | Contents |
| --- | --- |
| `DISCLAIMER.txt` | Explicit “not a certified audit” notice |
| `runbook.md` | This cadence (copy) |
| `controls.csv` | TSC criterion → product feature → evidence pointer |
| `users.csv` | Users **without** passwords or TOTP secrets |
| `access_matrix.csv` | Effective RBAC + User Rights per resource |
| `permission_overrides.csv` | Sparse `UserPermission` rows |
| `settings_snapshot.csv` | Settings KV with secret keys **omitted** |
| `api_keys.csv` | Name, hint, active flag — **no** key hashes |
| `audit_sample.csv` | Up to 500 most recent audit rows |
| `modules.csv` | Installed module IDs |
| `manifest.csv` / `meta.txt` | File list + tenant / generator metadata |

Financial close evidence (trial balance, GL, aging) is a **separate** download
from Period Close → auditor ZIP (`GET /api/periods/{id}/audit-pack`). This pack
does not replace that.

## Controls mapped (summary)

- **CC6.1** Logical access — JWT, bcrypt, optional TOTP, API keys
- **CC6.2 / CC6.3** Provisioning and removal — Team invites, deactivate, key revoke
- **CC6.6** Encryption in transit — operator TLS (outside the app)
- **CC6.7** Secrets at rest — bcrypt / Fernet TOTP / write-only Settings keys
- **CC7.2** Monitoring — `AuditLog`
- **CC8.1** Change management — git + in-app updates
- **A1.2** Backup — SQLite admin backup; cloud backups on Postgres
- **C1.1** Confidentiality — secret keys redacted from GET settings and this ZIP

CSV cells are formula-injection-safe (`services/export_utils.safe_cell`).
