"""Signed standalone install license — unlock after the 15-day trial."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tests.test_standalone_trial import _stamp, _standalone


def _issue(lic, **kwargs):
    kwargs.setdefault("plan", "starter")
    return lic.issue_token(**kwargs)


def _ephemeral_keypair(monkeypatch) -> str:
    """Install a throwaway Ed25519 pair via env (never the shipped production key)."""
    seed = os.urandom(32)
    priv = Ed25519PrivateKey.from_private_bytes(seed)
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    monkeypatch.setenv("EB_LICENSE_SIGNING_SEED", seed.hex())
    monkeypatch.setenv("EB_LICENSE_PUBKEY_HEX", pub)
    return seed.hex()


def test_install_id_write_once(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic

    first = lic.ensure_install_id()
    second = lic.ensure_install_id()
    assert first == second
    assert (tmp_path / lic.INSTALL_ID_NAME).is_file()
    assert first == (tmp_path / lic.INSTALL_ID_NAME).read_text(encoding="utf-8").strip()


def test_forged_token_rejected(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    lic.ensure_install_id()
    try:
        lic.parse_token("EB1.not-valid.payload")
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code in ("license_malformed", "license_signature")


def test_wrong_install_id_rejected(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    lic.ensure_install_id()
    token = _issue(lic, install_id="00000000-0000-0000-0000-000000000000", email="owner@co.test")
    try:
        lic.activate_token(token, emails=[], selected_plan="starter")
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_install_id"
        assert not lic.is_licensed()


def test_email_must_match_owner_when_users_exist(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="clerk@co.test")
    try:
        lic.activate_token(token, emails=[("owner@co.test", "owner"), ("clerk@co.test", "viewer")], selected_plan="starter")
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_email"

    owner_token = _issue(lic, install_id=iid, email="owner@co.test")
    info = lic.activate_token(
        owner_token,
        emails=[("owner@co.test", "owner"), ("clerk@co.test", "viewer")],
        selected_plan="starter",
    )
    assert info["licensed"] is True
    assert info["email"] == "owner@co.test"
    assert lic.is_licensed() is True


def test_expired_license_does_not_unlock(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    iid = lic.ensure_install_id()
    ended = datetime.now(timezone.utc) - timedelta(days=1)
    token = _issue(lic, install_id=iid, email="owner@co.test", expires_at=ended)
    try:
        lic.activate_token(token, emails=[], selected_plan="starter")
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_expired"
        assert lic.is_licensed() is False


def test_license_unlocks_expired_trial(client, monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services import standalone_trial as st

    r = client.post("/api/auth/signup", json={
        "email": "owner.license@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "License Co",
    })
    assert r.status_code == 200, r.text

    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc) - timedelta(days=20))
    expired = tmp_path / st.EXPIRED_NAME
    if expired.exists():
        expired.unlink()
    assert client.post(
        "/api/auth/login",
        data={"username": "owner.license@co.test", "password": "pw12345678"},
    ).status_code == 403
    assert st.install_locked() is True

    status = client.get("/api/license/status")
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["licensed"] is False
    iid = body["install_id"]
    assert iid

    token = _issue(lic, install_id=iid, email="owner.license@co.test")
    activated = client.post("/api/license/activate", json={"token": token, "plan": "starter"})
    assert activated.status_code == 200, activated.text
    assert activated.json()["licensed"] is True
    assert st.install_locked() is False
    info = st.trial_info()
    assert info["expired"] is True
    assert info["locked"] is False
    assert info["licensed"] is True

    login = client.post(
        "/api/auth/login",
        data={"username": "owner.license@co.test", "password": "pw12345678"},
    )
    assert login.status_code == 200, login.text
    signup = client.post("/api/auth/signup", json={
        "email": "new.after-license@co.test",
        "password": "pw12345678",
        "full_name": "New",
        "company_name": "New Co",
    })
    assert signup.status_code == 200, signup.text


def test_license_plan_and_addons_apply_to_owner(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ENFORCE_MODULE_PLANS", "true")
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic

    r = client.post("/api/auth/signup", json={
        "email": "owner.planlic@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Plan Co",
    })
    assert r.status_code == 200, r.text
    iid = client.get("/api/license/status").json()["install_id"]
    token = _issue(lic,
        install_id=iid,
        email="owner.planlic@co.test",
        plan="pro",
        addons=["healthcare"],
    )
    activated = client.post("/api/license/activate", json={"token": token, "plan": "pro"})
    assert activated.status_code == 200, activated.text
    body = activated.json()
    assert body["licensed"] is True
    assert body["plan"] == "pro"
    assert "healthcare" in (body.get("addons") or [])
    assert body["commercial"]["applied"] is True
    assert body["commercial"]["plan"] == "pro"

    tok = client.post(
        "/api/auth/login",
        data={"username": "owner.planlic@co.test", "password": "pw12345678"},
    )
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    auth = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    usage = client.get("/api/billing/usage", headers=auth).json()
    assert usage["plan"] == "pro"
    assert "healthcare" in (usage.get("extra_addons") or [])
    listed = client.get("/api/modules", headers=auth).json()
    hrm = next(m for m in listed if m["id"] == "hrm")
    health = next(m for m in listed if m["id"] == "healthcare")
    spinning = next(m for m in listed if m["id"] == "spinning")
    assert hrm["installable"] is True
    assert health["installable"] is True
    assert spinning["installable"] is False
    assert client.post("/api/billing/checkout", headers=auth, json={"plan": "enterprise"}).status_code == 403


def test_issue_token_requires_paid_plan(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    iid = lic.ensure_install_id()
    try:
        lic.issue_token(install_id=iid, email="owner@co.test")
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_plan"
    token = lic.issue_token(install_id=iid, email="owner@co.test", plan="basic")
    payload = lic.parse_token(token)
    assert payload["plan"] == "starter"


def test_activate_requires_matching_category(client, monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic

    r = client.post("/api/auth/signup", json={
        "email": "owner.cat@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Cat Co",
    })
    assert r.status_code == 200, r.text
    iid = client.get("/api/license/status").json()["install_id"]
    token = _issue(lic, install_id=iid, email="owner.cat@co.test", plan="pro")
    missing = client.post("/api/license/activate", json={"token": token})
    assert missing.status_code == 422
    mismatch = client.post("/api/license/activate", json={"token": token, "plan": "starter"})
    assert mismatch.status_code == 400
    assert "Pro" in mismatch.json()["detail"]
    ok = client.post("/api/license/activate", json={"token": token, "plan": "pro"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["plan"] == "pro"


def test_activate_token_rejects_missing_or_mismatched_category(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="owner@co.test", plan="starter")
    try:
        lic.activate_token(token, emails=[], selected_plan=None)
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_plan"
        assert not lic.is_licensed()
    try:
        lic.activate_token(token, emails=[], selected_plan="enterprise")
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_plan_mismatch"
        assert "Basic" in str(exc)
        assert not lic.is_licensed()
    info = lic.activate_token(token, emails=[], selected_plan="basic")
    assert info["licensed"] is True
    assert info["plan"] == "starter"


def test_issue_token_rejects_unknown_addon(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services.standalone_license import LicenseError

    iid = lic.ensure_install_id()
    try:
        _issue(lic, install_id=iid, email="owner@co.test", plan="starter", addons=["not-a-module"])
        assert False, "expected LicenseError"
    except LicenseError as exc:
        assert exc.code == "license_addons"


def test_activate_rejects_other_email_while_locked(client, monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services import standalone_trial as st

    r = client.post("/api/auth/signup", json={
        "email": "owner.mismatch@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Mismatch Co",
    })
    assert r.status_code == 200, r.text
    _stamp(tmp_path / st.STAMP_NAME, datetime.now(timezone.utc) - timedelta(days=20))
    expired = tmp_path / st.EXPIRED_NAME
    if expired.exists():
        expired.unlink()
    assert st.install_locked() is True

    iid = client.get("/api/license/status").json()["install_id"]
    token = _issue(lic, install_id=iid, email="someone.else@co.test")
    bad = client.post("/api/license/activate", json={"token": token, "plan": "starter"})
    assert bad.status_code == 400
    assert "owner" in bad.json()["detail"].lower()
    assert st.install_locked() is True
    assert client.post(
        "/api/auth/login",
        data={"username": "owner.mismatch@co.test", "password": "pw12345678"},
    ).status_code == 403


def test_license_files_land_in_easy_books_not_backend(monkeypatch, tmp_path):
    home = tmp_path / "home"
    books = home / ".easy-books"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("EB_DATA_DIR", raising=False)
    monkeypatch.delenv("EB_PORTABLE", raising=False)
    monkeypatch.delenv("EB_CLOUD_DATA_DIR", raising=False)
    monkeypatch.setenv("EB_STANDALONE", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("EB_SKIP_DEMO_TRIAL", raising=False)
    _ephemeral_keypair(monkeypatch)

    from local_config import repo_root
    from services import standalone_license as lic

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="owner@co.test")
    lic.activate_token(token, emails=[], selected_plan="starter")
    assert lic.install_id_path().parent.resolve() == books.resolve()
    assert lic.license_path().parent.resolve() == books.resolve()
    assert (books / lic.INSTALL_ID_NAME).is_file()
    assert (books / lic.LICENSE_FILE_NAME).is_file()
    assert lic.license_path().parent.resolve() != (repo_root() / "backend").resolve()
    assert lic.is_licensed() is True


def test_activate_script_writes_license(monkeypatch, tmp_path, capsys):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from scripts.activate_license import main

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="owner@co.test")
    monkeypatch.delenv("EB_LICENSE_PLAN", raising=False)
    assert main(["--token", token]) == 1
    err = capsys.readouterr().err
    assert "Basic" in err
    assert not lic.is_licensed()
    assert main(["--token", token, "--plan", "basic"]) == 0
    out = capsys.readouterr().out
    assert "License activated" in out
    assert "Basic" in out
    assert str(tmp_path) in out
    assert lic.is_licensed() is True


def test_issue_and_activate_scripts_round_trip(monkeypatch, tmp_path, capsys):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from scripts.activate_license import main as activate_main

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="Owner@Co.Test")
    assert token.startswith("EB1.")
    assert activate_main(["--token", token, "--plan", "starter"]) == 0
    assert lic.is_licensed() is True
    assert lic.license_status()["email"] == "owner@co.test"


def test_activate_license_sh_rejects_empty_token(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from local_config import repo_root
    from services import standalone_license as lic

    env = os.environ.copy()
    env["EB_DATA_DIR"] = str(tmp_path)
    env["EB_STANDALONE"] = "true"
    env["APP_ENV"] = "local"
    env.pop("EB_LICENSE_TOKEN", None)

    script = repo_root() / "docs" / "Activate_License.sh"
    proc = subprocess.run(
        ["bash", str(script)],
        input="\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo_root()),
        timeout=60,
    )
    assert proc.returncode == 1
    assert "License token is required" in proc.stdout or "License token is required" in proc.stderr
    assert not lic.is_licensed()


def test_activate_license_sh_accepts_piped_token(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from local_config import repo_root
    from services import standalone_license as lic

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="owner@co.test")

    env = os.environ.copy()
    env["EB_DATA_DIR"] = str(tmp_path)
    env["EB_STANDALONE"] = "true"
    env["APP_ENV"] = "local"
    env.pop("EB_LICENSE_TOKEN", None)
    env.pop("EB_LICENSE_PLAN", None)

    script = repo_root() / "docs" / "Activate_License.sh"
    proc = subprocess.run(
        ["bash", str(script)],
        input=token + "\n1\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo_root()),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "License activated" in proc.stdout
    assert lic.is_licensed() is True


def test_activate_license_sh_rejects_missing_category(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from local_config import repo_root
    from services import standalone_license as lic

    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="owner@co.test")

    env = os.environ.copy()
    env["EB_DATA_DIR"] = str(tmp_path)
    env["EB_STANDALONE"] = "true"
    env["APP_ENV"] = "local"
    env.pop("EB_LICENSE_TOKEN", None)
    env.pop("EB_LICENSE_PLAN", None)

    script = repo_root() / "docs" / "Activate_License.sh"
    proc = subprocess.run(
        ["bash", str(script)],
        input=token + "\n\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo_root()),
        timeout=60,
    )
    assert proc.returncode == 1
    combined = proc.stdout + proc.stderr
    assert "Basic" in combined
    assert not lic.is_licensed()


def test_product_tree_does_not_ship_staff_issuer():
    """A client git install must not contain token-minting field tools."""
    from local_config import repo_root

    root = repo_root()
    assert not (root / "docs" / "Issue_License.sh").exists()
    assert not (root / "docs" / "Issue_License.bat").exists()
    assert not (root / "docs" / "LICENSE_ISSUER.md").exists()
    assert not (root / "backend" / "scripts" / "issue_license.py").exists()


def test_activate_field_scripts_have_no_secrets():
    from local_config import repo_root
    from services.standalone_license import LICENSE_PUBKEY_HEX
    from scripts.extend_trial import DEFAULT_PASSWORD_SHA256

    docs = repo_root() / "docs"
    bat = (docs / "Activate_License.bat").read_text(encoding="utf-8")
    sh = (docs / "Activate_License.sh").read_text(encoding="utf-8")
    for text in (bat, sh):
        assert "scripts.activate_license" in text
        assert "EB_LICENSE_TOKEN" in text
        assert "EB_LICENSE_PLAN" in text
        assert "1) Basic" in text
        assert "2) Pro" in text
        assert "3) Enterprise" in text
        assert "EB_DATA_DIR" in text
        assert ".easy-books" in text
        assert DEFAULT_PASSWORD_SHA256 not in text
        assert "EB_LICENSE_SIGNING_SEED" not in text
        assert "LICENSE_PUBKEY" not in text
    assert LICENSE_PUBKEY_HEX not in bat
    assert LICENSE_PUBKEY_HEX not in sh
    assert sh.startswith("#!/usr/bin/env bash")


def test_skip_env_still_unlocks_without_license_file(monkeypatch, tmp_path):
    _standalone(monkeypatch, tmp_path)
    monkeypatch.setenv("EB_SKIP_DEMO_TRIAL", "true")
    from services.standalone_trial import install_locked, demo_trial_expired

    assert demo_trial_expired() is False
    assert install_locked() is False


def test_force_expire_does_not_lock_licensed_copy(client, monkeypatch, tmp_path):
    """QA expire still writes latches; a valid license keeps the copy unlocked."""
    _standalone(monkeypatch, tmp_path)
    _ephemeral_keypair(monkeypatch)
    from services import standalone_license as lic
    from services import standalone_trial as st

    r = client.post("/api/auth/signup", json={
        "email": "owner.licensed-expire@co.test",
        "password": "pw12345678",
        "full_name": "Owner",
        "company_name": "Licensed Expire Co",
    })
    assert r.status_code == 200, r.text
    iid = lic.ensure_install_id()
    token = _issue(lic, install_id=iid, email="owner.licensed-expire@co.test")
    info = lic.activate_token(
        token,
        emails=[("owner.licensed-expire@co.test", "owner")],
        selected_plan="starter",
    )
    assert info["licensed"] is True

    expired = st.force_expire_trial()
    assert expired["expired"] is True
    assert expired["licensed"] is True
    assert expired["locked"] is False
    assert st.demo_trial_expired() is True
    assert st.install_locked() is False
    assert (tmp_path / st.EXPIRED_NAME).is_file()

    login = client.post(
        "/api/auth/login",
        data={"username": "owner.licensed-expire@co.test", "password": "pw12345678"},
    )
    assert login.status_code == 200, login.text
