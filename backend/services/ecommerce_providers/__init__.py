"""eCommerce provider registry (#305)."""
from __future__ import annotations

from services.ecommerce_providers.base import (
    EcommerceProvider, NormalizedLine, NormalizedOrder, NormalizedProduct,
)
from services.ecommerce_providers.mock import MockEcommerceProvider
from services.ecommerce_providers.shopify import ShopifyProvider
from services.ecommerce_providers.woocommerce import WooCommerceProvider

PROVIDERS: dict[str, EcommerceProvider] = {
    "mock": MockEcommerceProvider(),
    "shopify": ShopifyProvider(),
    "woocommerce": WooCommerceProvider(),
}


def get_provider(name: str) -> EcommerceProvider:
    key = (name or "").lower().strip()
    if key not in PROVIDERS:
        raise KeyError(f"Unknown ecommerce provider: {name}")
    return PROVIDERS[key]


__all__ = [
    "EcommerceProvider",
    "NormalizedLine",
    "NormalizedOrder",
    "NormalizedProduct",
    "PROVIDERS",
    "get_provider",
]
