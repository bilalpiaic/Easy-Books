"""Sliding-window limiter (#427).

Redis when REDIS_URL is set (shared across API replicas). In-memory fallback
for desktop. Redis errors fail **open** — login still has the DB throttle.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

_mem: dict[tuple, deque] = defaultdict(deque)
_redis = None
_redis_failed = False
_redis_url_seen = None


def reset_memory() -> None:
    _mem.clear()


def _redis_client():
    global _redis, _redis_failed, _redis_url_seen
    url = (os.environ.get("REDIS_URL") or "").strip()
    if url != _redis_url_seen:
        _redis = None
        _redis_failed = False
        _redis_url_seen = url
    if not url:
        return None
    if _redis_failed:
        return None
    if _redis is not None:
        return _redis
    try:
        import redis as redis_lib
        _redis = redis_lib.from_url(
            url,
            socket_timeout=0.2,
            socket_connect_timeout=0.2,
            decode_responses=True,
        )
        return _redis
    except Exception:
        _redis_failed = True
        return None


def allow(
    scope: str,
    identity,
    *,
    limit: int,
    window: float,
    memory: dict | None = None,
) -> bool:
    """Record one hit. Return True if under ``limit`` in ``window`` seconds."""
    if limit <= 0:
        return True
    client = _redis_client()
    if client is not None:
        try:
            key = f"eb:rl:{scope}:{identity}"
            now = time.time()
            member = f"{now}:{os.getpid()}:{time.monotonic_ns()}"
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, int(window) + 5)
            _nrem, _nadd, n, _exp = pipe.execute()
            return int(n) <= limit
        except Exception:
            return True  # fail-open
    buckets = memory if memory is not None else _mem
    bucket = buckets.setdefault(identity, deque())
    now = time.monotonic()
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
