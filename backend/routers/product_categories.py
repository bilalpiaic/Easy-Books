"""Product category CRUD with a hard 2-level depth cap (parent → sub)."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Product, ProductCategory
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/product-categories", tags=["product-categories"], dependencies=[perm_dep("product_categories")])


class CategoryIn(BaseModel):
    name: str
    parent_id: Optional[int] = None
    is_active: bool = True


def _owned(session, tenant_id, cat_id) -> ProductCategory:
    cat = session.get(ProductCategory, cat_id)
    if not cat or cat.tenant_id != tenant_id:
        raise HTTPException(404, "Category not found")
    return cat


@router.get("")
def list_categories(session: SessionDep, user: CurrentUserDep):
    """Return categories as a nested parent→children tree."""
    rows = session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
    ).all()
    by_parent: dict = {}
    for c in rows:
        by_parent.setdefault(c.parent_id, []).append(
            {"id": c.id, "name": c.name, "parent_id": c.parent_id, "is_active": c.is_active}
        )
    roots = by_parent.get(None, [])
    for r in roots:
        r["children"] = by_parent.get(r["id"], [])
    return roots


@router.post("")
def create_category(body: CategoryIn, session: SessionDep, user: WriteUserDep):
    if body.parent_id is not None:
        parent = _owned(session, user.tenant_id, body.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(400, "Categories support only two levels (parent → sub-category).")
    cat = ProductCategory(tenant_id=user.tenant_id, name=body.name.strip(),
                          parent_id=body.parent_id, is_active=body.is_active)
    session.add(cat)
    log_audit(session, user, "create", "product_category", None, {"name": cat.name})
    session.commit(); session.refresh(cat)
    return {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "is_active": cat.is_active}


@router.patch("/{cat_id}")
def update_category(cat_id: int, body: CategoryIn, session: SessionDep, user: WriteUserDep):
    cat = _owned(session, user.tenant_id, cat_id)
    if body.parent_id is not None:
        if body.parent_id == cat_id:
            raise HTTPException(400, "A category cannot be its own parent.")
        parent = _owned(session, user.tenant_id, body.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(400, "Categories support only two levels (parent → sub-category).")
        has_children = session.exec(
            select(ProductCategory).where(ProductCategory.parent_id == cat_id)
        ).first()
        if has_children:
            raise HTTPException(400, "Move or delete its sub-categories first.")
    cat.name = body.name.strip(); cat.parent_id = body.parent_id; cat.is_active = body.is_active
    session.add(cat); session.commit(); session.refresh(cat)
    return {"id": cat.id, "name": cat.name, "parent_id": cat.parent_id, "is_active": cat.is_active}


@router.delete("/{cat_id}")
def delete_category(cat_id: int, session: SessionDep, user: WriteUserDep):
    cat = _owned(session, user.tenant_id, cat_id)
    if session.exec(select(ProductCategory).where(ProductCategory.parent_id == cat_id)).first():
        raise HTTPException(400, "Delete its sub-categories first.")
    if session.exec(select(Product).where(Product.category_id == cat_id)).first():
        raise HTTPException(400, "Reassign products off this category first.")
    session.delete(cat); session.commit()
    return {"ok": True}
