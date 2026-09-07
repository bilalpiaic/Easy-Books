# Store listing assets (#307)

Reuse the PWA icons. These are listing **placeholders** until marketing
produces final artwork. Pixel sizes match Play / App Store minimums where
we can generate them from `frontend/public/icons/`.

| File | Use |
| --- | --- |
| `icon-192.png` | Adaptive / notification small |
| `icon-512.png` | Play hi-res icon (upscale to 512 is already this file) |
| `icon-512-maskable.png` | Android adaptive safe-zone |
| `apple-touch-icon.png` | iOS (180² — App Store still wants 1024² master) |
| `icon-1024.png` | App Store / Play master (generated when ImageMagick is available) |

## Play Console (minimum checklist)

- High-res icon 512×512 PNG (`icon-512.png`)
- Feature graphic 1024×500 — **not generated**; add before store submit
- Phone screenshots 16:9 or 9:16, at least 2
- Short description / full description (product copy, not in git)

## App Store Connect

- 1024×1024 icon (`icon-1024.png` if present, else upscale `icon-512.png`)
- 6.7" and 6.1" iPhone screenshots
- Privacy nutrition: push notifications (device token), account login

Do not commit screenshots that contain live tenant data.
