"""Daraz Open API–shaped adapter (#305).

Sandbox mode (access_token empty or ``sandbox``) returns deterministic
catalog/orders like the mock provider. Live HTTP uses the seller API when
credentials are present; failures raise RuntimeError for sync error status.
"""
from __future__ import annotations

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


class DarazProvider:
    name = "daraz"

    def _sandbox(self, connection: EcommerceConnection) -> bool:
        tok = (connection.access_token or "").strip().lower()
        return tok in ("", "sandbox", "test")

    def _get(self, connection: EcommerceConnection, path: str, params: dict | None = None) -> Any:
        if not (connection.access_token or "").strip():
            raise RuntimeError("Daraz access_token is required for live pulls")
        domain = (connection.shop_domain or "api.daraz.pk").strip().rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        url = f"{domain}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {connection.access_token}",
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
            raise RuntimeError(f"Daraz HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise RuntimeError(f"Daraz request failed: {exc}") from exc

    def list_orders(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedOrder]:
        if self._sandbox(connection):
            tid = connection.tenant_id
            cid = connection.id or 0
            base = date.today()
            return [
                NormalizedOrder(
                    external_order_id=f"daraz-{tid}-{cid}-9001",
                    order_number="DZ-9001",
                    order_date=base,
                    customer_name="Daraz Buyer",
                    customer_email="daraz-buyer@example.com",
                    currency="USD",
                    lines=(
                        NormalizedLine(
                            external_product_id=f"daraz-sku-A-{tid}",
                            sku="DZ-SKU-A",
                            title="Daraz Tote",
                            qty=Decimal("1"),
                            unit_price=Decimal("19.99"),
                        ),
                    ),
                    notes="Daraz sandbox order",
                ),
            ]

        params: dict[str, str] = {"limit": "50"}
        if since:
            params["created_after"] = since.isoformat()
        data = self._get(connection, "/orders/get", params)
        orders = data.get("data", {}).get("orders") if isinstance(data, dict) else data
        if not isinstance(orders, list):
            orders = []
        out: list[NormalizedOrder] = []
        for o in orders:
            lines = []
            for li in o.get("order_items") or o.get("items") or []:
                lines.append(NormalizedLine(
                    external_product_id=str(li.get("product_id") or li.get("sku_id") or li.get("sku") or ""),
                    sku=str(li.get("sku") or ""),
                    title=str(li.get("name") or li.get("product_name") or "Item"),
                    qty=_d(li.get("quantity") or 1),
                    unit_price=_d(li.get("item_price") or li.get("price")),
                ))
            created = str(o.get("created_at") or o.get("createdAt") or "")[:10]
            try:
                od = date.fromisoformat(created)
            except ValueError:
                od = date.today()
            out.append(NormalizedOrder(
                external_order_id=str(o.get("order_id") or o.get("order_number") or o.get("id")),
                order_number=str(o.get("order_number") or o.get("order_id") or ""),
                order_date=od,
                customer_name=str(o.get("customer_name") or o.get("buyer_name") or "Daraz Customer"),
                customer_email=str(o.get("email") or ""),
                currency=str(o.get("currency") or "PKR"),
                lines=tuple(lines),
            ))
        return out

    def list_products(
        self,
        session: Session,
        connection: EcommerceConnection,
    ) -> list[NormalizedProduct]:
        if self._sandbox(connection):
            tid = connection.tenant_id
            return [
                NormalizedProduct(
                    external_product_id=f"daraz-sku-A-{tid}",
                    sku="DZ-SKU-A",
                    title="Daraz Tote",
                    price=Decimal("19.99"),
                    stock_qty=Decimal("25"),
                ),
            ]
        data = self._get(connection, "/products/get", {"limit": "100"})
        products = data.get("data", {}).get("products") if isinstance(data, dict) else data
        if not isinstance(products, list):
            products = []
        out: list[NormalizedProduct] = []
        for p in products:
            out.append(NormalizedProduct(
                external_product_id=str(p.get("product_id") or p.get("id")),
                sku=str(p.get("seller_sku") or p.get("sku") or p.get("id")),
                title=str(p.get("name") or p.get("attributes", {}).get("name") or "Product"),
                price=_d(p.get("price") or p.get("salePrice")),
                stock_qty=_d(p.get("quantity")) if p.get("quantity") is not None else None,
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
        if self._sandbox(connection):
            return  # sandbox accepts silently
        # Live quantity update — best-effort; errors bubble to sync status.
        domain = (connection.shop_domain or "api.daraz.pk").strip().rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        url = f"{domain}/product/stock/update"
        body = json.dumps({
            "product_id": external_product_id,
            "quantity": int(qty),
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {connection.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except Exception as exc:
            raise RuntimeError(f"Daraz stock push failed: {exc}") from exc
