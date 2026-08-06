# eCommerce connectors (#305)

Installable module `ecommerce` (Apps → Operations).

## Providers

| Id | Auth | Notes |
|----|------|-------|
| `mock` | none | Demo catalog + 2 orders |
| `shopify` | Admin API access token | REST `2024-07` |
| `woocommerce` | Consumer key + secret | WC REST v3 |

## Flow

1. Connect store (`POST /api/ecommerce/connections`)
2. Auto-map products by SKU → `Product.code` (`…/products/auto-map`)
3. Sync orders → **draft** invoices (`…/sync`) — human posts later
4. Optional stock direction: `off` | `store_to_eb` | `eb_to_store`

Daraz and live inventory-level push for Shopify locations are deferred.
