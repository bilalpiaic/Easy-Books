"""healthcare module — patients, OPD, IPD, lab, procedures, hospital store

Revision ID: 0027_healthcare
Revises: d42ac2e7674d
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_healthcare"
down_revision = "9a704c7672d5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "hc_patient"):
        op.create_table(
            "hc_patient",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("customer_id", sa.Integer, nullable=True),
            sa.Column("mr_number", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("dob", sa.String, nullable=True),
            sa.Column("gender", sa.String, nullable=False, server_default="other"),
            sa.Column("blood_group", sa.String, nullable=True),
            sa.Column("cnic", sa.String, nullable=True),
            sa.Column("phone", sa.String, nullable=True),
            sa.Column("address", sa.String, nullable=True),
            sa.Column("emergency_contact", sa.String, nullable=True),
            sa.Column("allergies", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "mr_number", name="uq_hc_patient_mr_per_tenant"),
        )

    if not bind.dialect.has_table(bind, "hc_doctor"):
        op.create_table(
            "hc_doctor",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("employee_id", sa.Integer, nullable=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("specialization", sa.String, nullable=True),
            sa.Column("qualification", sa.String, nullable=True),
            sa.Column("phone", sa.String, nullable=True),
            sa.Column("opd_fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("consultation_account_id", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if not bind.dialect.has_table(bind, "hc_ward"):
        op.create_table(
            "hc_ward",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("ward_type", sa.String, nullable=False, server_default="general"),
            sa.Column("total_beds", sa.Integer, nullable=False, server_default="0"),
            sa.Column("daily_charge", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("revenue_account_id", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        )

    if not bind.dialect.has_table(bind, "hc_procedure_catalog"):
        op.create_table(
            "hc_procedure_catalog",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("category", sa.String, nullable=False, server_default="minor"),
            sa.Column("standard_fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("revenue_account_id", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if not bind.dialect.has_table(bind, "hc_lab_test"):
        op.create_table(
            "hc_lab_test",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("category", sa.String, nullable=False, server_default="other"),
            sa.Column("normal_range", sa.String, nullable=True),
            sa.Column("unit", sa.String, nullable=True),
            sa.Column("standard_fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("revenue_account_id", sa.Integer, nullable=True),
            sa.Column("product_id", sa.Integer, nullable=True),
            sa.Column("qty_per_test", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    # hc_admission must be created before hc_bed (circular FK — bed.current_admission_id)
    if not bind.dialect.has_table(bind, "hc_admission"):
        op.create_table(
            "hc_admission",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("patient_id", sa.Integer, nullable=False, index=True),
            sa.Column("doctor_id", sa.Integer, nullable=False),
            sa.Column("ward_id", sa.Integer, nullable=False),
            sa.Column("bed_id", sa.Integer, nullable=False),
            sa.Column("admission_number", sa.String, nullable=False, index=True),
            sa.Column("admission_date", sa.String, nullable=False),
            sa.Column("discharge_date", sa.String, nullable=True),
            sa.Column("diagnosis", sa.String, nullable=True),
            sa.Column("admission_type", sa.String, nullable=False, server_default="planned"),
            sa.Column("status", sa.String, nullable=False, server_default="admitted"),
            sa.Column("deposit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("deposit_transaction_id", sa.Integer, nullable=True),
            sa.Column("discharge_invoice_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "admission_number", name="uq_hc_admission_number_per_tenant"),
        )

    if not bind.dialect.has_table(bind, "hc_bed"):
        op.create_table(
            "hc_bed",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("ward_id", sa.Integer, nullable=False, index=True),
            sa.Column("bed_number", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False, server_default="available"),
            sa.Column("current_admission_id", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        )

    if not bind.dialect.has_table(bind, "hc_procedure_consumable"):
        op.create_table(
            "hc_procedure_consumable",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("procedure_id", sa.Integer, nullable=False, index=True),
            sa.Column("product_id", sa.Integer, nullable=False),
            sa.Column("qty_per_procedure", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.Column("location_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "hc_opd_token"):
        op.create_table(
            "hc_opd_token",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("doctor_id", sa.Integer, nullable=False, index=True),
            sa.Column("patient_id", sa.Integer, nullable=True),
            sa.Column("patient_name", sa.String, nullable=True),
            sa.Column("token_number", sa.Integer, nullable=False),
            sa.Column("visit_date", sa.String, nullable=False, index=True),
            sa.Column("status", sa.String, nullable=False, server_default="waiting"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "doctor_id", "visit_date", "token_number",
                                name="uq_hc_token_per_doctor_day"),
        )

    if not bind.dialect.has_table(bind, "hc_opd_visit"):
        op.create_table(
            "hc_opd_visit",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("token_id", sa.Integer, nullable=True),
            sa.Column("patient_id", sa.Integer, nullable=False, index=True),
            sa.Column("doctor_id", sa.Integer, nullable=False, index=True),
            sa.Column("visit_date", sa.String, nullable=False, index=True),
            sa.Column("visit_type", sa.String, nullable=False, server_default="first"),
            sa.Column("chief_complaint", sa.Text, nullable=True),
            sa.Column("diagnosis", sa.Text, nullable=True),
            sa.Column("vitals_json", sa.Text, nullable=True),
            sa.Column("advice", sa.Text, nullable=True),
            sa.Column("follow_up_date", sa.String, nullable=True),
            sa.Column("invoice_id", sa.Integer, nullable=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "hc_prescription"):
        op.create_table(
            "hc_prescription",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("visit_id", sa.Integer, nullable=False, index=True),
            sa.Column("patient_id", sa.Integer, nullable=False),
            sa.Column("doctor_id", sa.Integer, nullable=False),
            sa.Column("prescribed_date", sa.String, nullable=False),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if not bind.dialect.has_table(bind, "hc_prescription_item"):
        op.create_table(
            "hc_prescription_item",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("prescription_id", sa.Integer, nullable=False, index=True),
            sa.Column("medicine_name", sa.String, nullable=False),
            sa.Column("product_id", sa.Integer, nullable=True),
            sa.Column("dosage", sa.String, nullable=True),
            sa.Column("frequency", sa.String, nullable=True),
            sa.Column("duration", sa.String, nullable=True),
            sa.Column("route", sa.String, nullable=False, server_default="oral"),
            sa.Column("instructions", sa.Text, nullable=True),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.Column("dispensed_qty", sa.Numeric(18, 4), nullable=True),
            sa.Column("dispensed_by_id", sa.Integer, nullable=True),
            sa.Column("dispensed_at", sa.DateTime, nullable=True),
        )

    if not bind.dialect.has_table(bind, "hc_admission_charge"):
        op.create_table(
            "hc_admission_charge",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("admission_id", sa.Integer, nullable=False, index=True),
            sa.Column("charge_date", sa.String, nullable=False, index=True),
            sa.Column("charge_type", sa.String, nullable=False, server_default="bed"),
            sa.Column("description", sa.String, nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("procedure_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "hc_lab_order"):
        op.create_table(
            "hc_lab_order",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("patient_id", sa.Integer, nullable=False, index=True),
            sa.Column("doctor_id", sa.Integer, nullable=True),
            sa.Column("admission_id", sa.Integer, nullable=True),
            sa.Column("order_number", sa.String, nullable=False, index=True),
            sa.Column("order_date", sa.String, nullable=False, index=True),
            sa.Column("source", sa.String, nullable=False, server_default="walkin"),
            sa.Column("status", sa.String, nullable=False, server_default="ordered"),
            sa.Column("invoice_id", sa.Integer, nullable=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "order_number", name="uq_hc_lab_order_per_tenant"),
        )

    if not bind.dialect.has_table(bind, "hc_lab_order_item"):
        op.create_table(
            "hc_lab_order_item",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("lab_order_id", sa.Integer, nullable=False, index=True),
            sa.Column("test_id", sa.Integer, nullable=False),
            sa.Column("fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("result_value", sa.String, nullable=True),
            sa.Column("result_unit", sa.String, nullable=True),
            sa.Column("reference_range", sa.String, nullable=True),
            sa.Column("is_abnormal", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("resulted_at", sa.DateTime, nullable=True),
            sa.Column("resulted_by_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "hc_sample_collection"):
        op.create_table(
            "hc_sample_collection",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("lab_order_id", sa.Integer, nullable=False, index=True),
            sa.Column("collected_by_id", sa.Integer, nullable=True),
            sa.Column("collected_at", sa.DateTime, nullable=True),
            sa.Column("collection_point", sa.String, nullable=False, server_default="lab"),
            sa.Column("specimen_type", sa.String, nullable=False, server_default="blood"),
            sa.Column("barcode", sa.String, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("status", sa.String, nullable=False, server_default="collected"),
        )

    if not bind.dialect.has_table(bind, "hc_procedure_order"):
        op.create_table(
            "hc_procedure_order",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("patient_id", sa.Integer, nullable=False, index=True),
            sa.Column("doctor_id", sa.Integer, nullable=True),
            sa.Column("admission_id", sa.Integer, nullable=True),
            sa.Column("procedure_id", sa.Integer, nullable=False),
            sa.Column("order_date", sa.String, nullable=False),
            sa.Column("performed_date", sa.String, nullable=True),
            sa.Column("status", sa.String, nullable=False, server_default="ordered"),
            sa.Column("fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("invoice_id", sa.Integer, nullable=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "hc_store_issue"):
        op.create_table(
            "hc_store_issue",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("issue_number", sa.String, nullable=False, index=True),
            sa.Column("issue_date", sa.String, nullable=False, index=True),
            sa.Column("from_location_id", sa.Integer, nullable=False),
            sa.Column("to_location_id", sa.Integer, nullable=True),
            sa.Column("patient_id", sa.Integer, nullable=True),
            sa.Column("admission_id", sa.Integer, nullable=True),
            sa.Column("purpose", sa.String, nullable=False, server_default="ward"),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "issue_number", name="uq_hc_store_issue_per_tenant"),
        )

    if not bind.dialect.has_table(bind, "hc_store_issue_item"):
        op.create_table(
            "hc_store_issue_item",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("issue_id", sa.Integer, nullable=False, index=True),
            sa.Column("product_id", sa.Integer, nullable=False),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("charge_to_patient", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("charge_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )


def downgrade():
    for table in [
        "hc_store_issue_item", "hc_store_issue",
        "hc_procedure_order", "hc_sample_collection",
        "hc_lab_order_item", "hc_lab_order",
        "hc_admission_charge", "hc_prescription_item", "hc_prescription",
        "hc_opd_visit", "hc_opd_token",
        "hc_procedure_consumable", "hc_bed", "hc_admission",
        "hc_lab_test", "hc_procedure_catalog", "hc_ward",
        "hc_doctor", "hc_patient",
    ]:
        op.drop_table(table)
