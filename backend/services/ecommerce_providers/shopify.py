"""Shopify Admin REST adapter (#305) — API access token auth.

Uses Admin REST ``/orders.json`` and ``/products.json``. When credentials are
missing or the remote call fails, raises ``RuntimeError`` so sync marks error.
Live HTTP is opt-in; unit tests use the mock provider.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session

from models_ecommerce import EcommerceConnection
from services.ecommerce_providers.base import (
    NormalizedLine, NormalizedOrder, NormalizedProduct,
)


def _d(v: Any) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


class ShopifyProvider:
    name = "shopify"

    def _base(self, connection: EcommerceConnection) -> str:
        domain = (connection.shop_domain or "").strip().rstrip("/")
        if not domain:
            raise RuntimeError("Shopify shop_domain is required (e.g. mystore.myshopify.com)")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/admin/api/2024-07"

    def _get(self, connection: EcommerceConnection, path: str, params: dict | None = None) -> dict:
        if not (connection.access_token or "").strip():
            raise RuntimeError("Shopify access_token is required")
        url = f"{self._base(connection)}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "X-Shopify-Access-Token": connection.access_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Shopify HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise RuntimeError(f"Shopify request failed: {exc}") from exc

    def list_orders(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedOrder]:
        params: dict[str, str] = {"status": "any", "limit": "50"}
        if since:
            params["created_at_min"] = f"{since.isoformat()}T00:00:00Z"
        data = self._get(connection, "/orders.json", params)
        out: list[NormalizedOrder] = []
        for o in data.get("orders") or []:
            lines = []
            for li in o.get("line_items") or []:
                lines.append(NormalizedLine(
                    external_product_id=str(li.get("product_id") or li.get("variant_id") or li.get("sku") or ""),
                    sku=str(li.get("sku") or ""),
                    title=str(li.get("title") or li.get("name") or "Item"),
                    qty=_d(li.get("quantity")),
                    unit_price=_d(li.get("price")),
                ))
            created = str(o.get("created_at") or "")[:10]
            try:
                od = date.fromisoformat(created)
            except ValueError:
                od = date.today()
            cust = o.get("customer") or {}
            name = " ".join(filter(None, [
                cust.get("first_name"), cust.get("last_name"),
            ])).strip() or str(o.get("email") or "Shopify Customer")
            out.append(NormalizedOrder(
                external_order_id=str(o.get("id")),
                order_number=str(o.get("name") or o.get("order_number") or o.get("id")),
                order_date=od,
                customer_name=name,
                customer_email=str(cust.get("email") or o.get("email") or ""),
                currency=str(o.get("currency") or ""),
                lines=tuple(lines),
                notes=str(o.get("note") or ""),
            ))
        return out

    def list_products(
        self,
        session: Session,
        connection: EcommerceConnection,
    ) -> list[NormalizedProduct]:
        data = self._get(connection, "/products.json", {"limit": "100"})
        out: list[NormalizedProduct] = []
        for p in data.get("products") or []:
            variants = p.get("variants") or [{}]
            v0 = variants[0] if variants else {}
            out.append(NormalizedProduct(
                external_product_id=str(p.get("id")),
                sku=str(v0.get("sku") or p.get("handle") or p.get("id")),
                title=str(p.get("title") or "Product"),
                price=_d(v0.get("price")),
                stock_qty=_d(v0.get("inventory_quantity")) if v0.get("inventory_quantity") is not None else None,
            ))
        return out

    def push_stock(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        external_product_id: str,
        qty: Decimal,
    ) -> None:
        # Inventory levels need location_id — deferred; mark as no-op with note.
        return
