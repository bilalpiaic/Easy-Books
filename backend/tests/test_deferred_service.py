"""Unit + schema tests for deferred-revenue origination (#47)."""
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db as _db_module
from models import Product, Tenant


def test_product_create_accepts_deferred_flags(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Support Plan", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 24,
    }).json()
    assert p["is_deferred"] is True
    assert p["recognition_months"] == 24


def test_product_update_accepts_deferred_flags(client, admin_headers):
    h = admin_headers
    # Create a product without deferral
    p = client.post("/api/products", headers=h, json={
        "name": "Basic Plan", "product_type": "service",
        "default_rate": 100,
    }).json()

    # Update it to be deferred
    updated = client.put(f"/api/products/{p['id']}", headers=h, json={
        "name": "Basic Plan", "product_type": "service",
        "default_rate": 100, "is_deferred": True, "recognition_months": 18,
    }).json()

    assert updated["is_deferred"] is True
    assert updated["recognition_months"] == 18
