"""eCommerce connectors API (#305) — connect stores, map products, import orders."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from models import Product, Tenant
from models_ecommerce import EcommerceConnection, EcommerceOrderImport, EcommerceProductMap
from routers.common import CurrentUserDep, SessionDep, WriteUserDep
from routers.modules import _get_enabled
from services.ecommerce_providers import PROVIDERS, get_provider
from services.ecommerce_sync import auto_map_products, ser_connection, sync_orders
from services.permissions import perm_dep

router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce"])


def _require_ecom(session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "ecommerce" not in _get_enabled(tenant):
        raise HTTPException(403, "Install the eCommerce Connectors module first")


class ConnectIn(BaseModel):
    provider: str
    shop_domain: str = ""
    shop_name: str = ""
    access_token: str = ""
    api_secret: Optional[str] = None
    stock_sync_direction: str = "off"  # off | store_to_eb | eb_to_store
    default_customer_id: Optional[int] = None


class ConnectionPatch(BaseModel):
    shop_name: Optional[str] = None
    access_token: Optional[str] = None
    api_secret: Optional[str] = None
    stock_sync_direction: Optional[str] = None
    default_customer_id: Optional[int] = None
    is_active: Optional[bool] = None


class ProductMapIn(BaseModel):
    external_product_id: str
    external_sku: Optional[str] = None
    external_title: Optional[str] = None
    product_id: int


@router.get("/providers", dependencies=[perm_dep("ecommerce.connections", "view")])
def list_providers(user: CurrentUserDep, session: SessionDep):
    _require_ecom(session, user)
    return [
        {"id": "mock", "label": "Mock Store (demo)", "auth": "none"},
        {"id": "shopify", "label": "Shopify", "auth": "access_token"},
        {"id": "woocommerce", "label": "WooCommerce", "auth": "consumer_key_secret"},
        {"id": "daraz", "label": "Daraz", "auth": "access_token"},
    ]


@router.get("/connections", dependencies=[perm_dep("ecommerce.connections", "view")])
def list_connections(user: CurrentUserDep, session: SessionDep):
    _require_ecom(session, user)
    rows = session.exec(
        select(EcommerceConnection)
        .where(EcommerceConnection.tenant_id == user.tenant_id)
        .order_by(EcommerceConnection.id.desc())
    ).all()
    return [ser_connection(r) for r in rows]


@router.post("/connections", status_code=201, dependencies=[perm_dep("ecommerce.connections", "edit")])
def connect_store(user: WriteUserDep, session: SessionDep, body: ConnectIn):
    _require_ecom(session, user)
    provider = (body.provider or "").lower().strip()
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider}")
    direction = (body.stock_sync_direction or "off").lower()
    if direction not in ("off", "store_to_eb", "eb_to_store"):
        raise HTTPException(400, "stock_sync_direction must be off|store_to_eb|eb_to_store")

    domain = (body.shop_domain or "").strip()
    if provider == "mock" and not domain:
        domain = "mock.local"
    if provider == "daraz" and not domain:
        domain = "api.daraz.pk"

    token = body.access_token or ""
    if provider == "mock" and not token:
        token = "mock-token"
    if provider == "daraz" and not token:
        token = "sandbox"

    row = EcommerceConnection(
        tenant_id=user.tenant_id,
        provider=provider,
        shop_domain=domain,
        shop_name=(body.shop_name or domain or provider).strip(),
        access_token=token,
        api_secret=body.api_secret,
        stock_sync_direction=direction,
        default_customer_id=body.default_customer_id,
        is_active=True,
        sync_status="never",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return ser_connection(row)


@router.patch("/connections/{id}", dependencies=[perm_dep("ecommerce.connections", "edit")])
def patch_connection(id: int, user: WriteUserDep, session: SessionDep, body: ConnectionPatch):
    _require_ecom(session, user)
    row = session.exec(
        select(EcommerceConnection).where(
            EcommerceConnection.id == id,
            EcommerceConnection.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Connection not found")
    if body.shop_name is not None:
        row.shop_name = body.shop_name
    if body.access_token is not None:
        row.access_token = body.access_token
    if body.api_secret is not None:
        row.api_secret = body.api_secret
    if body.stock_sync_direction is not None:
        d = body.stock_sync_direction.lower()
        if d not in ("off", "store_to_eb", "eb_to_store"):
            raise HTTPException(400, "stock_sync_direction must be off|store_to_eb|eb_to_store")
        row.stock_sync_direction = d
    if body.default_customer_id is not None:
        row.default_customer_id = body.default_customer_id
    if body.is_active is not None:
        row.is_active = body.is_active
    session.add(row)
    session.commit()
    session.refresh(row)
    return ser_connection(row)


@router.delete("/connections/{id}", status_code=204, dependencies=[perm_dep("ecommerce.connections", "edit")])
def delete_connection(id: int, user: WriteUserDep, session: SessionDep):
    _require_ecom(session, user)
    row = session.exec(
        select(EcommerceConnection).where(
            EcommerceConnection.id == id,
            EcommerceConnection.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Connection not found")
    # cascade maps / imports manually for SQLite
    for m in session.exec(
        select(EcommerceProductMap).where(EcommerceProductMap.connection_id == id)
    ).all():
        session.delete(m)
    for o in session.exec(
        select(EcommerceOrderImport).where(EcommerceOrderImport.connection_id == id)
    ).all():
        session.delete(o)
    session.delete(row)
    session.commit()


@router.post("/connections/{id}/sync", dependencies=[perm_dep("ecommerce.orders", "edit")])
def sync_connection(id: int, user: WriteUserDep, session: SessionDep):
    _require_ecom(session, user)
    row = session.exec(
        select(EcommerceConnection).where(
            EcommerceConnection.id == id,
            EcommerceConnection.tenant_id == user.tenant_id,
            EcommerceConnection.is_active == True,  # noqa: E712
        )
    ).first()
    if not row:
        raise HTTPException(404, "Connection not found")
    try:
        return sync_orders(session, user, row)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/connections/{id}/imports", dependencies=[perm_dep("ecommerce.orders", "view")])
def list_imports(id: int, user: CurrentUserDep, session: SessionDep, limit: int = 50):
    _require_ecom(session, user)
    rows = session.exec(
        select(EcommerceOrderImport).where(
            EcommerceOrderImport.tenant_id == user.tenant_id,
            EcommerceOrderImport.connection_id == id,
        ).order_by(EcommerceOrderImport.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "external_order_id": r.external_order_id,
            "external_order_number": r.external_order_number,
            "invoice_id": r.invoice_id,
            "status": r.status,
            "error": r.error,
            "imported_at": r.imported_at.isoformat() if r.imported_at else None,
        }
        for r in rows
    ]


@router.get("/connections/{id}/products", dependencies=[perm_dep("ecommerce.products", "view")])
def list_remote_products(id: int, user: CurrentUserDep, session: SessionDep):
    _require_ecom(session, user)
    row = session.exec(
        select(EcommerceConnection).where(
            EcommerceConnection.id == id,
            EcommerceConnection.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Connection not found")
    try:
        products = get_provider(row.provider).list_products(session, row)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    maps = {
        m.external_product_id: m
        for m in session.exec(
            select(EcommerceProductMap).where(
                EcommerceProductMap.tenant_id == user.tenant_id,
                EcommerceProductMap.connection_id == id,
            )
        ).all()
    }
    return [
        {
            "external_product_id": p.external_product_id,
            "sku": p.sku,
            "title": p.title,
            "price": float(p.price),
            "stock_qty": float(p.stock_qty) if p.stock_qty is not None else None,
            "mapped_product_id": maps[p.external_product_id].product_id if p.external_product_id in maps else None,
        }
        for p in products
    ]


@router.post("/connections/{id}/products/auto-map", dependencies=[perm_dep("ecommerce.products", "edit")])
def auto_map(id: int, user: WriteUserDep, session: SessionDep):
    _require_ecom(session, user)
    row = session.exec(
        select(EcommerceConnection).where(
            EcommerceConnection.id == id,
            EcommerceConnection.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Connection not found")
    try:
        return auto_map_products(session, user, row)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/connections/{id}/products/map", status_code=201, dependencies=[perm_dep("ecommerce.products", "edit")])
def map_product(id: int, user: WriteUserDep, session: SessionDep, body: ProductMapIn):
    _require_ecom(session, user)
    row = session.exec(
        select(EcommerceConnection).where(
            EcommerceConnection.id == id,
            EcommerceConnection.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Connection not found")
    prod = session.get(Product, body.product_id)
    if not prod or prod.tenant_id != user.tenant_id:
        raise HTTPException(400, "Product not found")
    existing = session.exec(
        select(EcommerceProductMap).where(
            EcommerceProductMap.tenant_id == user.tenant_id,
            EcommerceProductMap.connection_id == id,
            EcommerceProductMap.external_product_id == body.external_product_id,
        )
    ).first()
    if existing:
        existing.product_id = body.product_id
        existing.external_sku = body.external_sku
        existing.external_title = body.external_title
        session.add(existing)
        session.commit()
        session.refresh(existing)
        m = existing
    else:
        m = EcommerceProductMap(
            tenant_id=user.tenant_id,
            connection_id=id,
            external_product_id=body.external_product_id,
            external_sku=body.external_sku,
            external_title=body.external_title,
            product_id=body.product_id,
        )
        session.add(m)
        session.commit()
        session.refresh(m)
    return {
        "id": m.id,
        "external_product_id": m.external_product_id,
        "product_id": m.product_id,
        "external_sku": m.external_sku,
    }
