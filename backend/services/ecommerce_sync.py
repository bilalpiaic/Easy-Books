"""Import store orders as draft invoices + product mapping (#305)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from models import Customer, Product
from models_ecommerce import EcommerceConnection, EcommerceOrderImport, EcommerceProductMap
from routers.invoices import InvoiceCreate, InvoiceLineCreate, create_invoice
from services.ecommerce_providers import get_provider
from services.money import D, ZERO


def _mask(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip()
    if len(t) <= 4:
        return "••••"
    return f"••••{t[-4:]}"


def ser_connection(c: EcommerceConnection) -> dict:
    return {
        "id": c.id,
        "provider": c.provider,
        "shop_domain": c.shop_domain,
        "shop_name": c.shop_name,
        "access_token_masked": _mask(c.access_token),
        "has_secret": bool(c.api_secret),
        "stock_sync_direction": c.stock_sync_direction or "off",
        "default_customer_id": c.default_customer_id,
        "is_active": c.is_active,
        "last_sync": c.last_sync.isoformat() if c.last_sync else None,
        "last_error": c.last_error,
        "sync_status": c.sync_status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def resolve_product(
    session: Session,
    tenant_id: int,
    connection_id: int,
    *,
    external_product_id: str,
    sku: str,
) -> Optional[Product]:
    """Prefer explicit map, then Product.code == SKU."""
    m = session.exec(
        select(EcommerceProductMap).where(
            EcommerceProductMap.tenant_id == tenant_id,
            EcommerceProductMap.connection_id == connection_id,
            EcommerceProductMap.external_product_id == external_product_id,
        )
    ).first()
    if m:
        return session.get(Product, m.product_id)
    code = (sku or "").strip()
    if code:
        return session.exec(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.code == code,
                Product.is_active == True,  # noqa: E712
            )
        ).first()
    return None


def ensure_customer(
    session: Session,
    user,
    connection: EcommerceConnection,
    *,
    name: str,
    email: str,
) -> Customer:
    if connection.default_customer_id:
        c = session.get(Customer, connection.default_customer_id)
        if c and c.tenant_id == user.tenant_id:
            return c
    # Match by email then name
    if email:
        c = session.exec(
            select(Customer).where(
                Customer.tenant_id == user.tenant_id,
                Customer.email == email,
            )
        ).first()
        if c:
            return c
    c = session.exec(
        select(Customer).where(
            Customer.tenant_id == user.tenant_id,
            Customer.name == name,
        )
    ).first()
    if c:
        return c
    c = Customer(
        tenant_id=user.tenant_id,
        name=name or "eCommerce Customer",
        email=email or None,
        is_active=True,
    )
    session.add(c)
    session.flush()
    return c


def sync_orders(session: Session, user, connection: EcommerceConnection) -> dict:
    """Pull orders → draft invoices. Idempotent on external_order_id."""
    provider = get_provider(connection.provider)
    try:
        orders = provider.list_orders(session, connection)
    except Exception as exc:
        connection.sync_status = "error"
        connection.last_error = str(exc)[:500]
        session.add(connection)
        session.commit()
        raise

    created: list[dict] = []
    skipped = 0
    for order in orders:
        existing = session.exec(
            select(EcommerceOrderImport).where(
                EcommerceOrderImport.tenant_id == user.tenant_id,
                EcommerceOrderImport.connection_id == connection.id,
                EcommerceOrderImport.external_order_id == order.external_order_id,
            )
        ).first()
        if existing:
            skipped += 1
            continue

        cust = ensure_customer(
            session, user, connection,
            name=order.customer_name, email=order.customer_email,
        )
        lines: list[InvoiceLineCreate] = []
        for li in order.lines:
            prod = resolve_product(
                session, user.tenant_id, connection.id or 0,
                external_product_id=li.external_product_id, sku=li.sku,
            )
            lines.append(InvoiceLineCreate(
                product_id=prod.id if prod else None,
                description=li.title or li.sku or "Store item",
                qty=D(li.qty),
                unit="pcs",
                rate=D(li.unit_price),
            ))
        if not lines:
            row = EcommerceOrderImport(
                tenant_id=user.tenant_id,
                connection_id=connection.id or 0,
                external_order_id=order.external_order_id,
                external_order_number=order.order_number,
                status="skipped",
                error="No line items",
            )
            session.add(row)
            skipped += 1
            continue

        inv_body = InvoiceCreate(
            customer_id=cust.id,
            issue_date=order.order_date.isoformat(),
            due_date=order.order_date.isoformat(),
            description=f"{connection.provider} order {order.order_number}",
            notes=order.notes or None,
            currency=order.currency or None,
            lines=lines,
        )
        inv = create_invoice(session, user, inv_body, BackgroundTasks())
        inv_id = inv["id"] if isinstance(inv, dict) else inv.id
        row = EcommerceOrderImport(
            tenant_id=user.tenant_id,
            connection_id=connection.id or 0,
            external_order_id=order.external_order_id,
            external_order_number=order.order_number,
            invoice_id=inv_id,
            status="imported",
        )
        session.add(row)
        created.append({
            "external_order_id": order.external_order_id,
            "order_number": order.order_number,
            "invoice_id": inv_id,
        })

    # Optional stock pull (store → EB): update Product.stock_qty from catalog when mapped
    stock_updated = 0
    direction = (connection.stock_sync_direction or "off").lower()
    if direction == "store_to_eb":
        try:
            products = provider.list_products(session, connection)
        except Exception:
            products = []
        for p in products:
            mapped = session.exec(
                select(EcommerceProductMap).where(
                    EcommerceProductMap.tenant_id == user.tenant_id,
                    EcommerceProductMap.connection_id == connection.id,
                    EcommerceProductMap.external_product_id == p.external_product_id,
                )
            ).first()
            prod = session.get(Product, mapped.product_id) if mapped else None
            if not prod and p.sku:
                prod = session.exec(
                    select(Product).where(
                        Product.tenant_id == user.tenant_id,
                        Product.code == p.sku,
                    )
                ).first()
            if prod and p.stock_qty is not None:
                prod.stock_qty = float(D(p.stock_qty))
                session.add(prod)
                stock_updated += 1
    elif direction == "eb_to_store":
        maps = session.exec(
            select(EcommerceProductMap).where(
                EcommerceProductMap.tenant_id == user.tenant_id,
                EcommerceProductMap.connection_id == connection.id,
            )
        ).all()
        for m in maps:
            prod = session.get(Product, m.product_id)
            if not prod:
                continue
            try:
                provider.push_stock(
                    session, connection,
                    external_product_id=m.external_product_id,
                    qty=D(prod.stock_qty or 0),
                )
                stock_updated += 1
            except Exception:
                pass

    connection.last_sync = datetime.utcnow()
    connection.sync_status = "ok"
    connection.last_error = None
    session.add(connection)
    session.commit()
    return {
        "created": created,
        "created_count": len(created),
        "skipped": skipped,
        "stock_updated": stock_updated,
        "connection": ser_connection(connection),
    }


def auto_map_products(session: Session, user, connection: EcommerceConnection) -> dict:
    """Pull catalog and map by SKU → Product.code when unique match."""
    provider = get_provider(connection.provider)
    products = provider.list_products(session, connection)
    linked = 0
    for p in products:
        sku = (p.sku or "").strip()
        if not sku:
            continue
        existing = session.exec(
            select(EcommerceProductMap).where(
                EcommerceProductMap.tenant_id == user.tenant_id,
                EcommerceProductMap.connection_id == connection.id,
                EcommerceProductMap.external_product_id == p.external_product_id,
            )
        ).first()
        if existing:
            continue
        prod = session.exec(
            select(Product).where(
                Product.tenant_id == user.tenant_id,
                Product.code == sku,
            )
        ).first()
        if not prod:
            continue
        session.add(EcommerceProductMap(
            tenant_id=user.tenant_id,
            connection_id=connection.id or 0,
            external_product_id=p.external_product_id,
            external_sku=sku,
            external_title=p.title,
            product_id=prod.id or 0,
        ))
        linked += 1
    session.commit()
    return {"linked": linked, "catalog_size": len(products)}
