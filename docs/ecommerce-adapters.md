# eCommerce connectors (#305)

Installable module `ecommerce` (Apps → Operations).

## Providers

| Id | Auth | Notes |
|----|------|-------|
| `mock` | none | Demo catalog + 2 orders |
| `shopify` | Admin API access token | REST `2024-07`; inventory push via `/inventory_levels/set.json` |
| `woocommerce` | Consumer key + secret | WC REST v3; stock push updates `stock_quantity` |
| `daraz` | Access token (`sandbox` OK) | Sandbox catalog/orders offline; live seller API when token set |

## Flow

1. Connect store (`POST /api/ecommerce/connections`)
2. Auto-map products by SKU → `Product.code` (`…/products/auto-map`)
3. Sync orders → **draft** invoices (`…/sync`) — human posts later
4. Optional stock direction: `off` | `store_to_eb` | `eb_to_store`

When `eb_to_store`, sync calls `provider.push_stock` for each mapped product.
Shopify resolves `inventory_item_id` + first active location (override with
`api_secret` JSON `{"location_id": N}`). Sandbox/test tokens no-op the push.
