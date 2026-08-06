"""Ship what's-new notices into every user's Alerts inbox.

When Easy-Books updates (new git commits on the running install), we store an
``AppUpdateNotice`` with an easy-language title/body and fan it out as
``UserAlert(kind='system')`` so:

* logged-in users see a popup + bell badge during the session (poll), and
* users who were logged out see the same on their next login.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from models import AppUpdateNotice, Settings, User, UserAlert
from services.alerts import emit_alert

_REPO = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_KEY = "app_update_notices_bootstrapped"
DEDUPE_PREFIX = "app_update:"
ENTITY_TYPE = "app_update"

# In-process cache so dashboard polls don't re-hit GitHub every 90s.
_commits_cache: list[dict] | None = None
_commits_cache_at: float = 0.0
_COMMITS_TTL = 30 * 60
_sync_lock_busy = False

# Conventional-commit → plain English label
_PREFIX_LABELS = (
    (re.compile(r"^feat(\([^)]*\))?:\s*", re.I), "New"),
    (re.compile(r"^fix(\([^)]*\))?:\s*", re.I), "Fix"),
    (re.compile(r"^perf(\([^)]*\))?:\s*", re.I), "Faster"),
    (re.compile(r"^docs(\([^)]*\))?:\s*", re.I), "Docs"),
    (re.compile(r"^chore(\([^)]*\))?:\s*", re.I), "Maintenance"),
    (re.compile(r"^refactor(\([^)]*\))?:\s*", re.I), "Improvement"),
    (re.compile(r"^style(\([^)]*\))?:\s*", re.I), "Polish"),
    (re.compile(r"^test(\([^)]*\))?:\s*", re.I), "Tests"),
    (re.compile(r"^ci(\([^)]*\))?:\s*", re.I), "Build"),
    (re.compile(r"^build(\([^)]*\))?:\s*", re.I), "Build"),
)


def humanize_commit(message: str) -> tuple[str, str]:
    """Turn a git subject into (title, body) in everyday language."""
    raw = (message or "").strip()
    if not raw:
        return ("App update", "Easy-Books was updated with the latest improvements.")

    # Drop PR numbers / trailing issue refs for friendlier copy
    cleaned = re.sub(r"\s*\(#\d+\)\s*$", "", raw).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    label = "Update"
    rest = cleaned
    for pat, lab in _PREFIX_LABELS:
        m = pat.match(cleaned)
        if m:
            label = lab
            rest = cleaned[m.end():].strip()
            break

    # Capitalize first letter of the remainder
    if rest:
        rest = rest[0].upper() + rest[1:]
    else:
        rest = "Small improvements under the hood."

    # Keep titles short for the popup / bell
    title = f"{label}: {rest}"
    if len(title) > 90:
        title = title[:87].rstrip() + "…"

    body = (
        f"{rest} "
        "Open Easy-Books as usual — your books and data stay safe."
    )
    if len(body) > 240:
        body = body[:237].rstrip() + "…"
    return title, body


def _git_log(limit: int = 8) -> list[dict]:
    import os
    import time

    global _commits_cache, _commits_cache_at
    now = time.time()
    if _commits_cache is not None and (now - _commits_cache_at) < _COMMITS_TTL:
        return _commits_cache[:limit]

    out: list[dict] = []
    try:
        raw = subprocess.run(
            [
                "git", "log", f"--max-count={limit}",
                "--pretty=format:%h|%s|%as",
            ],
            capture_output=True, text=True, cwd=str(_REPO), timeout=3,
        ).stdout.strip()
    except Exception:
        raw = ""
    for line in (raw or "").splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) >= 2:
            out.append({
                "sha": parts[0],
                "message": parts[1],
                "date": parts[2] if len(parts) > 2 else "",
            })

    # Cloud / packaged installs often have no .git — fall back to GitHub
    # with a hard short timeout so serverless never burns the whole request.
    if not out and os.environ.get("UPDATE_NOTICES_GITHUB", "true").lower() not in (
        "0", "false", "no", "off",
    ):
        out = _github_log(limit=limit)

    _commits_cache = out
    _commits_cache_at = now
    return out[:limit]


def _github_log(limit: int = 8) -> list[dict]:
    import json
    import socket
    import urllib.error
    import urllib.request

    url = (
        "https://api.github.com/repos/bilalpiaic/Easy-Books/commits"
        f"?sha=main&per_page={max(1, min(limit, 8))}"
    )
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Easy-Books-UpdateNotices",
            },
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (socket.timeout, TimeoutError, urllib.error.URLError, Exception):
        return []
    out: list[dict] = []
    for row in data if isinstance(data, list) else []:
        sha = str(row.get("sha") or "")[:7]
        msg = str((row.get("commit") or {}).get("message") or "").split("\n", 1)[0]
        date = str((row.get("commit") or {}).get("author", {}).get("date") or "")[:10]
        if sha and msg:
            out.append({"sha": sha, "message": msg, "date": date})
    return out


def ensure_notice_table(session: Session) -> None:
    """Create ``app_update_notice`` if missing (Vercel often skips Alembic)."""
    from sqlalchemy import inspect

    bind = session.get_bind()
    try:
        if inspect(bind).has_table("app_update_notice"):
            return
    except Exception:
        pass
    try:
        AppUpdateNotice.__table__.create(bind, checkfirst=True)
    except Exception:
        # Concurrent cold starts may race; subsequent selects will succeed.
        pass


def _is_bootstrapped(session: Session) -> bool:
    # Any tenant setting or any notice counts as bootstrapped.
    try:
        if session.exec(select(AppUpdateNotice).limit(1)).first():
            return True
    except Exception:
        session.rollback()
        ensure_notice_table(session)
        if session.exec(select(AppUpdateNotice).limit(1)).first():
            return True
    row = session.exec(
        select(Settings).where(Settings.key == BOOTSTRAP_KEY).limit(1)
    ).first()
    return bool(row and row.value == "1")


def _mark_bootstrapped(session: Session) -> None:
    # Store on the lowest tenant_id so the flag survives; ignore if no tenants yet.
    from models import Tenant
    t = session.exec(select(Tenant).order_by(Tenant.id).limit(1)).first()  # type: ignore
    if not t:
        return
    existing = session.exec(
        select(Settings).where(
            Settings.tenant_id == t.id,
            Settings.key == BOOTSTRAP_KEY,
        )
    ).first()
    if existing:
        existing.value = "1"
        session.add(existing)
    else:
        session.add(Settings(tenant_id=t.id, key=BOOTSTRAP_KEY, value="1"))


def _active_users(session: Session) -> list[User]:
    return list(session.exec(
        select(User).where(User.is_active == True)  # noqa: E712
    ).all())


def fanout_notice(session: Session, notice: AppUpdateNotice) -> int:
    """Create a system alert for every active user (dedupe by sha)."""
    from datetime import datetime

    key = f"{DEDUPE_PREFIX}{notice.sha}"
    users = _active_users(session)
    if not users:
        return 0
    existing_ids = set(session.exec(
        select(UserAlert.user_id).where(UserAlert.dedupe_key == key)
    ).all())
    now = datetime.utcnow()
    batch: list[UserAlert] = []
    for u in users:
        if u.id in existing_ids:
            continue
        batch.append(UserAlert(
            tenant_id=u.tenant_id,
            user_id=u.id,  # type: ignore[arg-type]
            kind="system",
            severity="info",
            title=notice.title,
            body=notice.body,
            href="/alerts",
            entity_type=ENTITY_TYPE,
            entity_id=notice.id,
            dedupe_key=key,
            created_at=now,
        ))
    if not batch:
        return 0
    session.add_all(batch)
    session.flush()
    return len(batch)


def sync_update_notices(
    session: Session,
    *,
    limit: int = 8,
    force_fanout: bool = False,
) -> dict:
    """Upsert notices from recent git commits and fan out to users.

    First run after this feature ships records the current HEAD history
    without spamming everyone. Later new commits create alerts.
    """
    global _sync_lock_busy
    if _sync_lock_busy and not force_fanout:
        return {"created": 0, "alerted": 0, "skipped": "busy"}
    _sync_lock_busy = True
    try:
        return _sync_update_notices_inner(
            session, limit=limit, force_fanout=force_fanout
        )
    finally:
        _sync_lock_busy = False


def _sync_update_notices_inner(
    session: Session,
    *,
    limit: int = 8,
    force_fanout: bool = False,
) -> dict:
    ensure_notice_table(session)

    commits = _git_log(limit=limit)
    if not commits:
        return {"created": 0, "alerted": 0, "bootstrapped": _is_bootstrapped(session)}

    bootstrapped = _is_bootstrapped(session)
    created_notices: list[AppUpdateNotice] = []

    for c in commits:
        sha = c["sha"]
        exists = session.exec(
            select(AppUpdateNotice).where(AppUpdateNotice.sha == sha)
        ).first()
        if exists:
            continue
        title, body = humanize_commit(c["message"])
        notice = AppUpdateNotice(
            sha=sha,
            title=title,
            body=body,
            commit_date=c.get("date") or None,
            # Quiet seed on first feature deploy; alert only for later commits.
            notify_users=bootstrapped,
        )
        session.add(notice)
        session.flush()
        created_notices.append(notice)

    alerted = 0
    if not bootstrapped:
        # Seed quietly — users shouldn't get 8 historical popups on first deploy.
        _mark_bootstrapped(session)
        session.commit()
        return {"created": len(created_notices), "alerted": 0, "bootstrapped": False}

    if created_notices or force_fanout:
        targets = [n for n in created_notices if n.notify_users]
        if force_fanout and not targets:
            latest = session.exec(
                select(AppUpdateNotice)
                .where(AppUpdateNotice.notify_users == True)  # noqa: E712
                .order_by(AppUpdateNotice.id.desc())  # type: ignore
                .limit(1)
            ).first()
            targets = [latest] if latest else []
        # Cap fan-out work per request (serverless time budget).
        for notice in targets[:2]:
            alerted += fanout_notice(session, notice)
        session.commit()

    return {"created": len(created_notices), "alerted": alerted, "bootstrapped": True}


def ensure_user_notices(session: Session, user: User, *, limit: int = 3) -> int:
    """Backfill recent notify-able notices for this user (late join / missed fanout)."""
    try:
        notices = session.exec(
            select(AppUpdateNotice)
            .where(AppUpdateNotice.notify_users == True)  # noqa: E712
            .order_by(AppUpdateNotice.id.desc())  # type: ignore
            .limit(limit)
        ).all()
    except Exception:
        session.rollback()
        return 0
    n = 0
    for notice in notices:
        if emit_alert(
            session,
            tenant_id=user.tenant_id,
            user_id=user.id,  # type: ignore[arg-type]
            kind="system",
            severity="info",
            title=notice.title,
            body=notice.body,
            href="/alerts",
            entity_type=ENTITY_TYPE,
            entity_id=notice.id,
            dedupe_key=f"{DEDUPE_PREFIX}{notice.sha}",
        ):
            n += 1
    if n:
        session.commit()
    return n


def unread_update_alerts(session: Session, user: User) -> list[UserAlert]:
    try:
        ensure_user_notices(session, user)
    except Exception:
        session.rollback()
    return list(session.exec(
        select(UserAlert)
        .where(
            UserAlert.user_id == user.id,
            UserAlert.tenant_id == user.tenant_id,
            UserAlert.kind == "system",
            UserAlert.entity_type == ENTITY_TYPE,
            UserAlert.read_at.is_(None),  # type: ignore[attr-defined]
        )
        .order_by(UserAlert.created_at.desc())  # type: ignore
    ).all())


def ack_update_alerts(session: Session, user: User, alert_ids: Optional[list[int]] = None) -> int:
    from datetime import datetime

    q = select(UserAlert).where(
        UserAlert.user_id == user.id,
        UserAlert.tenant_id == user.tenant_id,
        UserAlert.kind == "system",
        UserAlert.entity_type == ENTITY_TYPE,
        UserAlert.read_at.is_(None),  # type: ignore[attr-defined]
    )
    if alert_ids:
        q = q.where(UserAlert.id.in_(alert_ids))  # type: ignore[attr-defined]
    rows = list(session.exec(q).all())
    now = datetime.utcnow()
    for a in rows:
        a.read_at = now
        session.add(a)
    if rows:
        session.commit()
    return len(rows)
