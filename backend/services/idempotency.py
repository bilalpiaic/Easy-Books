"""Idempotency-Key middleware.

Per-tenant cache of POST responses, keyed by the client-supplied
`Idempotency-Key` header. Replays return the cached body+status without
re-executing the handler. Reads (GET/HEAD) and unkeyed requests bypass the
cache.

The tenant is resolved by decoding the bearer token / cookie inline — we
can't depend on FastAPI's dep system here because middleware runs before
deps. Failures to decode pass through (the auth dep will reject the request
downstream anyway).
"""
import json as _json
import os
from typing import Optional

from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from sqlmodel import Session, select

from auth import ALGORITHM, SECRET_KEY
from db import engine as _default_engine


_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _resolve_tenant_id(request: Request) -> Optional[int]:
    auth_header = request.headers.get("authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("eb_access")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("tenant_id")
    except JWTError:
        return None


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in _MUTATING:
            return await call_next(request)
        key = request.headers.get("idempotency-key")
        if not key:
            return await call_next(request)
        tenant_id = _resolve_tenant_id(request)
        if tenant_id is None:
            # Let downstream auth reject it
            return await call_next(request)

        # Resolve engine — tests can override via app.state.engine
        engine = getattr(request.app.state, "engine", None) or _default_engine

        # Lookup
        from models import IdempotencyKey  # local import — avoids circular at boot
        with Session(engine) as s:
            existing = s.exec(
                select(IdempotencyKey).where(
                    IdempotencyKey.tenant_id == tenant_id,
                    IdempotencyKey.key == key,
                )
            ).first()
            if existing:
                return JSONResponse(
                    content=_json.loads(existing.response_body),
                    status_code=existing.status_code,
                    headers={"Idempotency-Replay": "true"},
                )

        response: Response = await call_next(request)

        # Only cache successful 2xx responses
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            # Re-yield the body so the client still receives it
            response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            try:
                parsed = _json.loads(body.decode("utf-8")) if body else None
            except (UnicodeDecodeError, _json.JSONDecodeError):
                parsed = None
            if parsed is not None:
                engine_after = getattr(request.app.state, "engine", None) or _default_engine
                with Session(engine_after) as s:
                    s.add(
                        IdempotencyKey(
                            tenant_id=tenant_id,
                            key=key,
                            method=request.method,
                            path=request.url.path,
                            status_code=response.status_code,
                            response_body=_json.dumps(parsed),
                        )
                    )
                    try:
                        s.commit()
                    except Exception:
                        # Race: another worker beat us to it. Surface their
                        # cached response on the next call; not fatal here.
                        s.rollback()
        return response
