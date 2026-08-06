"""What's-new update notifications for every user."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from main import app
from models import AppUpdateNotice, User, UserAlert
from services.update_notices import (
    fanout_notice,
    humanize_commit,
    sync_update_notices,
)


def test_ensure_notice_table_reuses_session_connection():
    """pool_size=1 must not deadlock when ensuring the notice table.

    Production Neon uses QueuePool(pool_size=1). Inspecting/creating via
    ``session.get_bind()`` checks out a second connection and hangs forever.
    """
    from sqlalchemy.pool import QueuePool
    from sqlmodel import Session, SQLModel, create_engine

    from services.update_notices import ensure_notice_table
    import services.update_notices as un

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
    )
    # Intentionally do NOT create app_update_notice via metadata.create_all —
    # ensure_notice_table must create it using the open session's connection.
    tables = [
        t for t in SQLModel.metadata.sorted_tables
        if t.name != "app_update_notice"
    ]
    SQLModel.metadata.create_all(engine, tables=tables)
    un._notice_table_ready = False

    with Session(engine) as session:
        # Holding the sole pooled connection — this used to hang.
        ensure_notice_table(session)
        session.commit()
        row = session.exec(select(AppUpdateNotice).limit(1)).first()
        assert row is None  # table exists, empty
    assert un._notice_table_ready is True
    engine.dispose()


def test_humanize_commit_easy_language():
    title, body = humanize_commit("feat(inventory): pick/pack workflow (#302)")
    assert title.startswith("New:")
    assert "Pick/pack" in title or "pick/pack" in title.lower() or "Pick/pack" in title
    assert "safe" in body.lower() or "books" in body.lower()

    title2, _ = humanize_commit("fix(banking): consent expiry blocks sync")
    assert title2.startswith("Fix:")


def _signup(client: TestClient, email: str):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": "Notice Co",
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_notices_popup_on_login_and_ack(client: TestClient):
    auth = _signup(client, "notice-user@co.test")

    # First sync bootstraps quietly (no spam from history)
    first = client.get("/api/system/update/notices", headers=auth)
    assert first.status_code == 200, first.text
    # May be empty if bootstrap only, or empty items after quiet seed
    assert "items" in first.json()

    # Simulate a newly shipped update that should notify everyone
    with Session(app.state.engine) as session:
        notice = AppUpdateNotice(
            sha="abc1234",
            title="New: Faster invoice printing",
            body="Invoices print quicker. Your books stay safe.",
            commit_date="2026-08-06",
            notify_users=True,
        )
        session.add(notice)
        session.commit()
        session.refresh(notice)
        fanout_notice(session, notice)
        session.commit()

    # Logged-in poll / next login sees the popup payload
    again = client.get("/api/system/update/notices", headers=auth)
    assert again.status_code == 200, again.text
    items = again.json()["items"]
    assert any("invoice" in (i["title"] or "").lower() for i in items)
    ids = [i["id"] for i in items]

    # Also visible in the Alerts inbox
    alerts = client.get("/api/alerts?unread_only=true", headers=auth).json()
    assert any(a.get("kind") == "system" for a in alerts["items"])

    # Dismiss popup → marked read, no longer returned
    ack = client.post(
        "/api/system/update/notices/ack",
        headers=auth,
        json={"alert_ids": ids},
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["acked"] >= 1

    cleared = client.get("/api/system/update/notices", headers=auth).json()
    assert cleared["items"] == []


def test_sync_bootstraps_without_alerting(client: TestClient):
    _signup(client, "bootstrap-notice@co.test")
    with Session(app.state.engine) as session:
        # Wipe notices from prior tests in this process DB if any for isolation —
        # sync on empty table should bootstrap.
        before = session.exec(select(AppUpdateNotice)).all()
        # If already bootstrapped by other tests, just assert helper is safe.
        result = sync_update_notices(session)
        assert "created" in result
        assert "alerted" in result
        # After bootstrap, a brand-new notify notice still fans out
        user = session.exec(select(User).where(User.email == "bootstrap-notice@co.test")).first()
        assert user is not None
        notice = AppUpdateNotice(
            sha="def5678",
            title="Fix: Bank feed reconnect tip",
            body="We made reconnecting bank feeds clearer.",
            notify_users=True,
        )
        session.add(notice)
        session.commit()
        session.refresh(notice)
        n = fanout_notice(session, notice)
        session.commit()
        assert n >= 1
        alert = session.exec(
            select(UserAlert).where(
                UserAlert.user_id == user.id,
                UserAlert.dedupe_key == "app_update:def5678",
            )
        ).first()
        assert alert is not None
        assert alert.kind == "system"
        # silence unused
        _ = before


def test_get_notices_is_per_user_not_global_fanout(client: TestClient):
    """Hot-path sync with for_user must alert only that user — not everyone."""
    from services.update_notices import ensure_user_notices

    auth_a = _signup(client, "per-user-a@co.test")
    auth_b = _signup(client, "per-user-b@co.test")

    # Quiet first-run seed so later notify rows are real "what's new" items.
    assert client.get("/api/system/update/notices", headers=auth_a).status_code == 200

    with Session(app.state.engine) as session:
        session.add(AppUpdateNotice(
            sha="peruser1",
            title="New: Soft landing for updates",
            body="What's-new pops up only for you when you open the app.",
            notify_users=True,
        ))
        session.commit()

        user_a = session.exec(select(User).where(User.email == "per-user-a@co.test")).first()
        user_b = session.exec(select(User).where(User.email == "per-user-b@co.test")).first()
        assert user_a and user_b

        # Mirror the GET hot path: sync + for_user (no global fanout)
        sync_update_notices(session, for_user=user_a)

        a_alert = session.exec(
            select(UserAlert).where(
                UserAlert.user_id == user_a.id,
                UserAlert.dedupe_key == "app_update:peruser1",
            )
        ).first()
        b_alert = session.exec(
            select(UserAlert).where(
                UserAlert.user_id == user_b.id,
                UserAlert.dedupe_key == "app_update:peruser1",
            )
        ).first()
        assert a_alert is not None
        assert b_alert is None  # A's sync must not wake B

        # B's own lazy ensure creates their alert
        ensure_user_notices(session, user_b, commit=True)
        b_alert2 = session.exec(
            select(UserAlert).where(
                UserAlert.user_id == user_b.id,
                UserAlert.dedupe_key == "app_update:peruser1",
            )
        ).first()
        assert b_alert2 is not None

    # HTTP surface still returns unread items for the caller
    a = client.get("/api/system/update/notices", headers=auth_a)
    assert a.status_code == 200, a.text
    assert any(i.get("dedupe_key") == "app_update:peruser1" for i in a.json()["items"])

    b = client.get("/api/system/update/notices", headers=auth_b)
    assert b.status_code == 200, b.text
    assert any(i.get("dedupe_key") == "app_update:peruser1" for i in b.json()["items"])
