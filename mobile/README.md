# Easy-Books mobile shell (Capacitor)

Thin **iOS + Android** WebView around the existing Next.js PWA (#226 / #307).
This is **not** a React Native rewrite. Offline UX is the same Serwist service
worker, `/~offline` fallback, and `OfflineBanner` already in the web app.

## Point the WebView at the PWA

```bash
cd mobile
npm ci
export CAPACITOR_SERVER_URL=https://your-easy-books-host
npx cap add android   # once
npx cap add ios       # once, on macOS for Xcode
npx cap sync
npx cap open android
npx cap open ios
```

`FRONTEND_ORIGIN` on the API must include that host. Capacitor local origins
(`capacitor://localhost`, `https://localhost`) are always added to CORS.

## Push (overdue / approvals)

After login, `CapacitorPush` in the dashboard layout requests permission and
`POST /api/devices` with the FCM/APNs token.

`emit_alert` fans out **only** for `overdue_invoice` and `approval_needed`.
Delivery:

| Env | Behaviour |
| --- | --- |
| unset | Hook runs, status `skipped_no_provider` (default / CI) |
| `PUSH_WEBHOOK_URL` | JSON POST `{token, platform, title, body, data}` |
| `FCM_SERVER_KEY` | Legacy FCM HTTP `https://fcm.googleapis.com/fcm/send` |

Tapping a notification opens `data.href` (same paths as the in-app bell).

## Store listing assets

See `store/STORE_LISTING.md`. Icons are copied from `frontend/public/icons/`.

## Signed builds in CI

`mobile/scripts/ci-signed-build.sh` is wired into `.github/workflows/release.yml`.

- **Without** `ANDROID_KEYSTORE_BASE64`: job succeeds after `cap sync` and
  prints that signing secrets are not configured. It does **not** claim an
  App Store / Play upload.
- **With** keystore secrets: `./gradlew bundleRelease` if the Android SDK is
  on the runner.

iOS IPA signing still requires a macOS runner + Apple secrets (same pattern
as Electron notarization in `release.yml`).
