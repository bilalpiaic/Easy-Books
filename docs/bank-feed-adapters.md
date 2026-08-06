# Bank feed provider adapters (#301)

Easy-Books normalizes every bank feed onto `NormalizedTxn` before writing
`StatementLine` rows via `upsert_feed_transactions`.

## Field mapping (EU/UK Open Banking → NormalizedTxn)

| NormalizedTxn | Berlin Group / OBIE source | Notes |
|---|---|---|
| `external_id` | `transactionId` / `entryReference` | De-dupe key |
| `booking_date` | `bookingDate` (prefer over `valueDate`) | Matching window |
| `amount` | signed amount in account currency | **Positive = money OUT** (Plaid convention) |
| `remittance` | unstructured `remittanceInformation` | Merchant text usually lives here |
| `counterparty_name` / `counterparty_iban` | creditor/debtor account | Optional |

## Providers today

| Key | Module | Live pull |
|---|---|---|
| `plaid` | `services.bank_providers.plaid_adapter` | HTTP in `routers/bank_feeds.py` (`/transactions/sync`) |
| `mock` | `services.bank_providers.mock` | Deterministic sample remittance txns for demo/tests |

## Sync model

PSD2 / Open Banking AIS is **pull-only** — there are no bank-side webhooks.
Use:

1. On-demand `POST /api/banking/feeds/{id}/sync`
2. Scheduled `BANK_SYNC_ENABLED` loop in `main.py` (`BANK_SYNC_INTERVAL_HOURS`, default 24)

Consent expiry (typically 90 days) is stored on `PlaidConnection.consent_expires_at`
and surfaces as `sync_status=consent_expired` — distinct from a failed pull
(`sync_status=error` + `last_error`).

## Adding a real EU/UK aggregator

1. Implement `BankFeedProvider.list_transactions` in `services/bank_providers/`
2. Register it in `PROVIDERS`
3. Add a connect endpoint that stores encrypted credentials + `consent_expires_at`
4. Keep upsert + match/rules paths unchanged

Candidates that fit “no own aggregator network”: Enable Banking, Tink, Yapily, Salt Edge.
