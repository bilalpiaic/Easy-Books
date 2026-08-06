"""WooCommerce REST adapter (#305) — consumer key + secret.

Uses WC REST ``/wp-json/wc/v3/orders`` and ``/products``.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
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


class WooCommerceProvider:
    name = "woocommerce"

    def _base(self, connection: EcommerceConnection) -> str:
        domain = (connection.shop_domain or "").strip().rstrip("/")
        if not domain:
            raise RuntimeError("WooCommerce shop_domain is required (e.g. https://shop.example.com)")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/wp-json/wc/v3"

    def _get(self, connection: EcommerceConnection, path: str, params: dict | None = None) -> Any:
        key = (connection.access_token or "").strip()
        secret = (connection.api_secret or "").strip()
        if not key or not secret:
            raise RuntimeError("WooCommerce consumer key (access_token) and secret are required")
        url = f"{self._base(connection)}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        token = base64.b64encode(f"{key}:{secret}".encode()).decode()
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Basic {token}",
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
            raise RuntimeError(f"WooCommerce HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise RuntimeError(f"WooCommerce request failed: {exc}") from exc

    def list_orders(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedOrder]:
        params: dict[str, str] = {"per_page": "50", "orderby": "date", "order": "desc"}
        if since:
            params["after"] = f"{since.isoformat()}T00:00:00"
        data = self._get(connection, "/orders", params)
        if not isinstance(data, list):
            data = []
        out: list[NormalizedOrder] = []
        for o in data:
            lines = []
            for li in o.get("line_items") or []:
                lines.append(NormalizedLine(
                    external_product_id=str(li.get("product_id") or li.get("sku") or ""),
                    sku=str(li.get("sku") or ""),
                    title=str(li.get("name") or "Item"),
                    qty=_d(li.get("quantity")),
                    unit_price=_d(li.get("price")),
                ))
            created = str(o.get("date_created") or "")[:10]
            try:
                od = date.fromisoformat(created)
            except ValueError:
                od = date.today()
            billing = o.get("billing") or {}
            name = " ".join(filter(None, [
                billing.get("first_name"), billing.get("last_name"),
            ])).strip() or str(billing.get("email") or "Woo Customer")
            out.append(NormalizedOrder(
                external_order_id=str(o.get("id")),
                order_number=str(o.get("number") or o.get("id")),
                order_date=od,
                customer_name=name,
                customer_email=str(billing.get("email") or ""),
                currency=str(o.get("currency") or ""),
                lines=tuple(lines),
                notes=str(o.get("customer_note") or ""),
            ))
        return out

    def list_products(
        self,
        session: Session,
        connection: EcommerceConnection,
    ) -> list[NormalizedProduct]:
        data = self._get(connection, "/products", {"per_page": "100"})
        if not isinstance(data, list):
            data = []
        out: list[NormalizedProduct] = []
        for p in data:
            out.append(NormalizedProduct(
                external_product_id=str(p.get("id")),
                sku=str(p.get("sku") or p.get("id")),
                title=str(p.get("name") or "Product"),
                price=_d(p.get("price") or p.get("regular_price")),
                stock_qty=_d(p.get("stock_quantity")) if p.get("stock_quantity") is not None else None,
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
        return
