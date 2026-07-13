"""#137 P1 carry-in (+ a healthcare twin found while fixing it): two mutual FK
cycles exist — ComparativeStatement.po_id <-> PurchaseOrder.comparative_id and
HcBed.current_admission_id <-> HcAdmission.bed_id. Until broken,
SQLModel.metadata.sorted_tables emits an SAWarning and returns an arbitrary
order for the cycle members — which the demo-purge endpoint (routers/admin.py)
relies on for FK-safe deletes. Harmless on SQLite, a hard FK error on Postgres.

Fix under test: the nullable back-pointer of each cycle (po_id,
current_admission_id) is declared with use_alter=True so the sort excludes
that edge, making the order deterministic: the forward-referencing table
sorts later and reversed() deletes its rows first (the purge additionally
nulls the back-pointers before deleting).
"""
import warnings

from sqlalchemy import exc as sa_exc
from sqlmodel import SQLModel


def test_sorted_tables_emits_no_cycle_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error", sa_exc.SAWarning)
        list(SQLModel.metadata.sorted_tables)  # must not raise


def test_purge_delete_order_removes_po_before_comparative():
    delete_order = [t.name for t in reversed(SQLModel.metadata.sorted_tables)]
    assert delete_order.index("purchaseorder") < delete_order.index(
        "comparativestatement"
    ), "PO rows (holding comparative_id) must be deleted before CS rows"


def test_purge_delete_order_removes_admission_before_bed():
    delete_order = [t.name for t in reversed(SQLModel.metadata.sorted_tables)]
    assert delete_order.index("hc_admission") < delete_order.index(
        "hc_bed"
    ), "admission rows (holding bed_id) must be deleted before bed rows"
