"""§2 — JournalEntry carries customer_id/vendor_id; Account carries party_type.
   §3 — FixedAsset carries acquisition_transaction_id."""
from models import JournalEntry, Account, FixedAsset


def test_journal_entry_has_customer_id():
    fields = JournalEntry.model_fields
    assert "customer_id" in fields
    assert fields["customer_id"].default is None


def test_journal_entry_has_vendor_id():
    fields = JournalEntry.model_fields
    assert "vendor_id" in fields
    assert fields["vendor_id"].default is None


def test_account_has_party_type():
    fields = Account.model_fields
    assert "party_type" in fields
    assert fields["party_type"].default is None


def test_fixed_asset_has_acquisition_transaction_id():
    fields = FixedAsset.model_fields
    assert "acquisition_transaction_id" in fields
    assert fields["acquisition_transaction_id"].default is None
