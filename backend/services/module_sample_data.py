"""Optional sample-data seeding when a module is installed from Add-ons.

Reuses the idempotent helpers in scripts.seed_demo so install+seed is safe
to re-run. Default is off for real tenants; Apps UI opts in for the demo.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from models import Customer, Product, Settings, User, Vendor


def _set_setting(session: Session, tenant_id: int, key: str, value: str) -> None:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    if row:
        row.value = value
        session.add(row)
    else:
        session.add(Settings(key=key, value=value, tenant_id=tenant_id))


def _get_setting_value(session: Session, tenant_id: int, key: str) -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else ""


def _ensure_party(session: Session, tenant_id: int) -> tuple[list[Customer], list[Vendor]]:
    """Weaving seed needs at least one customer; create stubs if the company is empty."""
    customers = list(session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all())
    vendors = list(session.exec(select(Vendor).where(Vendor.tenant_id == tenant_id)).all())
    if not customers:
        c = Customer(tenant_id=tenant_id, name="Sample Customer", email="sample.customer@example.com")
        session.add(c)
        session.flush()
        customers = [c]
    if not vendors:
        v = Vendor(tenant_id=tenant_id, name="Sample Vendor", email="sample.vendor@example.com")
        session.add(v)
        session.flush()
        vendors = [v]
    return customers, vendors


def seed_module_sample(session: Session, user: User, module_id: str) -> dict[str, Any]:
    """Seed sample rows for *module_id* on the current tenant. Idempotent.

    Returns a small status dict for the install API response.
    Unknown / non-seedable modules return ``{"seeded": False, "reason": "..."}``.
    """
    # Lazy import keeps the hot install path light when seed_sample=false.
    from scripts import seed_demo as sd

    tid = user.tenant_id
    try:
        if module_id == "telecom":
            sd._seed_telecom_franchise(session, user)
        elif module_id == "healthcare":
            sd._seed_healthcare(session, user)
            sd._seed_dialysis(session, user)
        elif module_id == "pra":
            sd._seed_pra_settings(session, tid)
            sd._seed_pra_customers(session, tid)
            sd._seed_pra_products(session, tid)
            sd._seed_pra_submission_logs(session, tid)
        elif module_id == "uae_vat":
            from services.uae_einvoice import ensure_uae_tax_and_coa
            ensure_uae_tax_and_coa(session, tid)
            _set_setting(session, tid, "uae_vat_enabled", "true")
            _set_setting(session, tid, "uae_sandbox_mode", "true")
            if not _get_setting_value(session, tid, "uae_trn"):
                _set_setting(session, tid, "uae_trn", "100000000000003")
            if not _get_setting_value(session, tid, "uae_legal_name"):
                _set_setting(session, tid, "uae_legal_name", "Demo UAE Trading LLC")
        elif module_id == "sa_zatca":
            _set_setting(session, tid, "zatca_enabled", "true")
            _set_setting(session, tid, "zatca_sandbox_mode", "true")
            if not _get_setting_value(session, tid, "zatca_vat_number"):
                _set_setting(session, tid, "zatca_vat_number", "300000000000003")
            if not _get_setting_value(session, tid, "zatca_cr_number"):
                _set_setting(session, tid, "zatca_cr_number", "1010000000")
            if not _get_setting_value(session, tid, "zatca_device_id"):
                _set_setting(session, tid, "zatca_device_id", "EGS1-8888")
        elif module_id == "in_gst":
            from services.india_gst import ensure_india_gst_tax_and_coa
            ensure_india_gst_tax_and_coa(session, tid)
            _set_setting(session, tid, "in_gst_enabled", "true")
            if not _get_setting_value(session, tid, "in_state_code"):
                _set_setting(session, tid, "in_state_code", "27")
            if not _get_setting_value(session, tid, "in_gstin"):
                _set_setting(session, tid, "in_gstin", "27AAAAA0000A1Z5")
        elif module_id == "uk_mtd":
            _set_setting(session, tid, "uk_mtd_enabled", "true")
            _set_setting(session, tid, "uk_mtd_sandbox_mode", "true")
            if not _get_setting_value(session, tid, "uk_mtd_vrn"):
                _set_setting(session, tid, "uk_mtd_vrn", "123456789")
            if not _get_setting_value(session, tid, "currency"):
                _set_setting(session, tid, "currency", "GBP")
            if not _get_setting_value(session, tid, "country"):
                _set_setting(session, tid, "country", "GB")
        elif module_id == "my_invois":
            _set_setting(session, tid, "my_invois_enabled", "true")
            _set_setting(session, tid, "my_invois_sandbox_mode", "true")
            if not _get_setting_value(session, tid, "my_invois_tin"):
                _set_setting(session, tid, "my_invois_tin", "C12345678901")
            if not _get_setting_value(session, tid, "currency"):
                _set_setting(session, tid, "currency", "MYR")
            if not _get_setting_value(session, tid, "country"):
                _set_setting(session, tid, "country", "MY")
        elif module_id == "eu_peppol":
            _set_setting(session, tid, "peppol_enabled", "true")
            _set_setting(session, tid, "peppol_sandbox_mode", "true")
            if not _get_setting_value(session, tid, "peppol_participant_id"):
                _set_setting(session, tid, "peppol_participant_id", "0088:1234567890123")
            if not _get_setting_value(session, tid, "peppol_ap_url"):
                _set_setting(
                    session, tid, "peppol_ap_url",
                    "https://api.peppol-sandbox.example/v1/send",
                )
            if not _get_setting_value(session, tid, "currency"):
                _set_setting(session, tid, "currency", "EUR")
            if not _get_setting_value(session, tid, "country"):
                _set_setting(session, tid, "country", "NL")
        elif module_id == "weaving":
            customers, vendors = _ensure_party(session, tid)
            sd._seed_weaving(session, user, customers, vendors)
        elif module_id == "weighbridge":
            customers, vendors = _ensure_party(session, tid)
            sd._seed_weighbridge(session, user, customers, vendors)
        elif module_id == "spinning":
            customers, vendors = _ensure_party(session, tid)
            sd._seed_spinning(session, user, customers, vendors, stock_products=[])
        elif module_id == "textile_processing":
            customers, vendors = _ensure_party(session, tid)
            sd._seed_textile_processing(session, user, customers, vendors)
        elif module_id == "hrm":
            components = sd._seed_salary_components(session, tid)
            employees = sd._seed_employees(session, tid, "simple")
            if employees and components:
                sd._seed_salary_structures(session, employees, components)
                sd._seed_attendance(session, tid, employees)
        elif module_id == "inventory":
            if not session.exec(select(Product).where(Product.tenant_id == tid)).first():
                sd._seed_products(session, tid, "trader")
        elif module_id == "pos":
            from models_pos import PosRegister
            from services.pos import ensure_walk_in_customer, resolve_default_cash_account
            if not session.exec(select(Product).where(Product.tenant_id == tid)).first():
                sd._seed_products(session, tid, "trader")
            ensure_walk_in_customer(session, tid)
            if not session.exec(
                select(PosRegister).where(PosRegister.tenant_id == tid)
            ).first():
                session.add(
                    PosRegister(
                        tenant_id=tid,
                        name="Front Counter",
                        code="REG1",
                        cash_account_id=resolve_default_cash_account(session, tid),
                    )
                )
        elif module_id in ("production", "purchase_store", "ai_assistant"):
            return {
                "seeded": False,
                "reason": (
                    f"{module_id} sample data is available via "
                    "Settings → Sample / Demo Data"
                ),
            }
        else:
            return {"seeded": False, "reason": f"no sample seeder for {module_id}"}

        session.commit()
        return {"seeded": True, "module": module_id}
    except Exception as exc:  # noqa: BLE001 — never fail the install on sample seed
        session.rollback()
        print(f"[module_sample_data] seed failed for {module_id}: {exc}")
        return {"seeded": False, "reason": str(exc)[:200]}


def enable_pra_settings(session: Session, tenant_id: int) -> None:
    """Turn on sandbox PRA flags when the pra module is installed."""
    _set_setting(session, tenant_id, "pra_enabled", "true")
    _set_setting(session, tenant_id, "pra_sandbox_mode", "true")
    session.commit()


def enable_uae_vat_settings(session: Session, tenant_id: int) -> None:
    """Turn on sandbox UAE VAT + seed tax codes / CoA leaves on install."""
    from services.uae_einvoice import ensure_uae_tax_and_coa

    ensure_uae_tax_and_coa(session, tenant_id)
    _set_setting(session, tenant_id, "uae_vat_enabled", "true")
    _set_setting(session, tenant_id, "uae_sandbox_mode", "true")
    session.commit()


def enable_zatca_settings(session: Session, tenant_id: int) -> None:
    """Turn on sandbox ZATCA flags when the sa_zatca module is installed."""
    _set_setting(session, tenant_id, "zatca_enabled", "true")
    _set_setting(session, tenant_id, "zatca_sandbox_mode", "true")
    session.commit()


def enable_india_gst_settings(session: Session, tenant_id: int) -> None:
    """Turn on India GST + seed CGST/SGST/IGST tax codes on install."""
    from services.india_gst import enable_india_gst_settings as _enable

    _enable(session, tenant_id)


def enable_uk_mtd_settings(session: Session, tenant_id: int) -> None:
    """Turn on sandbox HMRC MTD flags when the uk_mtd module is installed."""
    _set_setting(session, tenant_id, "uk_mtd_enabled", "true")
    _set_setting(session, tenant_id, "uk_mtd_sandbox_mode", "true")
    session.commit()


def enable_my_invois_settings(session: Session, tenant_id: int) -> None:
    """Turn on sandbox MyInvois flags when the my_invois module is installed."""
    _set_setting(session, tenant_id, "my_invois_enabled", "true")
    _set_setting(session, tenant_id, "my_invois_sandbox_mode", "true")
    session.commit()
