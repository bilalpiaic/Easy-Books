# Native mobile shell (Capacitor on the PWA)

Easy-Books ships a **Capacitor** iOS/Android wrapper in `mobile/`. It loads
the existing PWA (Serwist, `OfflineBanner`, `/~offline`). `/api/*` stays
`NetworkOnly` in `frontend/src/app/sw.ts`.

Push: after login, native shells `POST /api/devices`. Overdue invoices and
approval-needed alerts fan out through `services/push.py`. Without
`FCM_SERVER_KEY` or `PUSH_WEBHOOK_URL` the hook is a no-op send
(`skipped_no_provider`). See `mobile/README.md`.
