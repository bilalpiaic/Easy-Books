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


def test_membership_backfill_quotes_reserved_user_table():
    """Postgres treats unquoted `user` as a function, not the table (#422 CI)."""
    src = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0044_tenant_membership.py"
    ).read_text()
    assert 'quote("user")' in src
    assert "FROM user" not in src.replace('quote("user")', "")


def test_env_widens_alembic_version_num_for_long_revision_ids():
    """Postgres alembic_version.version_num is VARCHAR(32) by default."""
    env = (Path(__file__).resolve().parents[1] / "alembic" / "env.py").read_text()
    assert "VARCHAR(128)" in env
    script = _script()
    long_ids = [rev.revision for rev in script.walk_revisions() if len(rev.revision) > 32]
    assert "0048_hc_patient_email_lab_publish" in long_ids
    assert all(len(r) <= 128 for r in long_ids)


def test_quoted_user_identifier_roundtrips_sqlite(tmp_path):
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{tmp_path}/u.db")
    q = engine.dialect.identifier_preparer.quote("user")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {q} (id INTEGER, tenant_id INTEGER, role TEXT)"))
        conn.execute(text(f"INSERT INTO {q} (id, tenant_id, role) VALUES (1, 2, 'owner')"))
        row = conn.execute(text(f"SELECT id, tenant_id, role FROM {q}")).one()
    assert row == (1, 2, "owner")
