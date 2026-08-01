"""Third-party extension manifest schema (#227).

v1 is **declarative only** — manifests never carry executable code.
Install records the snapshot on the tenant and may enable first-party
``requires_modules``; it never imports, evals, or downloads scripts.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# partner.<publisher>.<slug> — mirrors reverse-DNS extension IDs
_EXT_ID = re.compile(r"^partner\.[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$")
_SEMVER = re.compile(r"^\d+\.\d+\.\d+([.-][A-Za-z0-9._-]+)?$")

# Capabilities an extension may *request*. Granting is recorded for audit /
# future enforcement — v1 does not execute partner code against these.
PermissionScope = Literal[
    "read_reports",
    "read_invoices",
    "read_bills",
    "read_customers",
    "read_vendors",
    "write_webhooks",
    "read_settings",
]


class ExtensionManifest(BaseModel):
    """Frozen contract between Easy-Books and a curated third-party listing."""

    id: str = Field(..., description="Stable reverse-DNS id, e.g. partner.acme.bank-csv")
    name: str
    version: str
    description: str
    publisher: str
    category: str = "Integrations"
    icon: str = "Package"
    homepage: str | None = None
    # First-party MODULE_REGISTRY ids that must be installed with this extension
    requires_modules: list[str] = Field(default_factory=list)
    requested_permissions: list[PermissionScope] = Field(default_factory=list)
    settings_keys: list[str] = Field(
        default_factory=list,
        description="Settings keys the extension may read/write via a future partner API.",
    )
    webhook_events: list[str] = Field(default_factory=list)
    # Optional deep-link shown in Apps after install (never an arbitrary script URL)
    docs_url: str | None = None
    curated: bool = True

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not _EXT_ID.match(v):
            raise ValueError(
                "id must match partner.<publisher>.<slug> "
                "(lowercase alphanumerics, hyphens, underscores)"
            )
        return v

    @field_validator("version")
    @classmethod
    def _semver(cls, v: str) -> str:
        if not _SEMVER.match(v):
            raise ValueError("version must be semver-like (e.g. 1.0.0)")
        return v

    @field_validator("settings_keys")
    @classmethod
    def _settings_prefix(cls, keys: list[str]) -> list[str]:
        for k in keys:
            if not k.startswith("ext."):
                raise ValueError(
                    f"settings key {k!r} must start with 'ext.' "
                    "(partner namespace — never overwrite core settings)"
                )
        return keys

    @field_validator("homepage", "docs_url")
    @classmethod
    def _https_only(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not (v.startswith("https://") or v.startswith("http://localhost")):
            raise ValueError("URLs must be https:// (or http://localhost for dev)")
        return v


class CatalogEntry(BaseModel):
    """One row in the curated marketplace catalog."""

    manifest: ExtensionManifest
    # When set, Install maps to first-party MODULE_REGISTRY install instead
    first_party_module: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)


class InstalledExtension(BaseModel):
    id: str
    version: str
    installed_at: str
    publisher: str
    name: str
    requested_permissions: list[str]
    requires_modules: list[str]
    docs_url: str | None = None
    source: Literal["curated", "remote"] = "curated"
