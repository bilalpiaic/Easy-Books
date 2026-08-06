"""Bank feed provider adapters (#301).

Normalize provider-specific transaction payloads onto ``NormalizedTxn`` before
``services.plaid_sync.upsert_feed_transactions`` writes StatementLines.
"""
from __future__ import annotations

from services.bank_providers.base import BankFeedProvider, NormalizedTxn
from services.bank_providers.mock import MockOpenBankingProvider
from services.bank_providers.openbanking import OpenBankingProvider
from services.bank_providers.plaid_adapter import PlaidProvider

PROVIDERS: dict[str, BankFeedProvider] = {
    "mock": MockOpenBankingProvider(),
    "openbanking": OpenBankingProvider(),
    "plaid": PlaidProvider(),
}


def get_provider(name: str) -> BankFeedProvider:
    key = (name or "plaid").lower()
    if key not in PROVIDERS:
        raise KeyError(f"Unknown bank feed provider: {name}")
    return PROVIDERS[key]


__all__ = [
    "BankFeedProvider",
    "NormalizedTxn",
    "MockOpenBankingProvider",
    "OpenBankingProvider",
    "PlaidProvider",
    "PROVIDERS",
    "get_provider",
]
