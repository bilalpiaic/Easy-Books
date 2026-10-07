"""Client IP behind a reverse proxy (#427).

``TRUSTED_PROXIES`` is a comma-separated list of IPs or CIDRs. Default is
``127.0.0.1``. ``X-Forwarded-For`` is honoured only when the immediate peer
is on that list — a spoofed header from the public internet is ignored.
"""
from __future__ import annotations

import ipaddress
import os

from fastapi import Request


def trusted_proxy_list() -> list[str]:
    raw = os.environ.get("TRUSTED_PROXIES")
    if raw is None:
        return ["127.0.0.1"]
    return [p.strip() for p in raw.split(",") if p.strip()]


def _peer_is_trusted(peer: str, trusted: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        # TestClient uses the hostname "testclient"; only trust it if listed.
        return peer in trusted
    for item in trusted:
        try:
            if "/" in item:
                if addr in ipaddress.ip_network(item, strict=False):
                    return True
            elif addr == ipaddress.ip_address(item):
                return True
        except ValueError:
            if peer == item:
                return True
    return False


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = trusted_proxy_list()
    if not _peer_is_trusted(peer, trusted):
        return peer
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return peer
