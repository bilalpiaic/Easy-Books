"""#422 — Alembic graph stays a single head; duplicate filename prefixes are frozen."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

# Historical filename prefixes that collide (0023/0024/0025/0027). Revision
# *ids* are unique; do not rename these files on an installed database.
_GRANDFATHERED_PREFIXES = {
    "0023": ("0023_employees.py", "0023_analytic_account_links.py"),
    "0024": ("0024_payroll.py", "0024_party_links_asset_jv.py"),
    "0025": ("0025_attendance.py", "0025_product_cost_method.py"),
    "0027": ("0027_healthcare.py", "0027_pra_buyer_fields.py"),
}


def _script() -> ScriptDirectory:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_alembic_has_exactly_one_head():
    heads = _script().get_heads()
    assert len(heads) == 1, f"expected 1 alembic head, got {heads}"


def test_grandfathered_duplicate_prefixes_still_present():
    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    names = {p.name for p in versions.glob("*.py")}
    for prefix, files in _GRANDFATHERED_PREFIXES.items():
        for name in files:
            assert name in names, f"do not rename grandfathered {prefix} file {name}"
