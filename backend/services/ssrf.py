"""SSRF guard for tenant-controlled URLs (#428).

Blocks private, loopback, link-local, and cloud metadata addresses.
DNS is resolved when possible; literal IPs are always checked. Redirects
must not be followed by callers (httpx default).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:127.0.0.0/104"),
    ipaddress.ip_network("::ffff:169.254.0.0/112"),
    ipaddress.ip_network("::ffff:10.0.0.0/104"),
    ipaddress.ip_network("::ffff:192.168.0.0/112"),
]

_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}


def _is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_loopback: bool) -> bool:
    if allow_loopback and (ip.is_loopback or ip.is_unspecified):
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_multicast or ip.is_reserved:
        return True
    mapped = ip
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        mapped = ip.ipv4_mapped
    return any(mapped in net or ip in net for net in _BLOCKED)


def public_url_error(url: str, *, allow_loopback: bool = False) -> str | None:
    """Return a user-facing error, or None if the URL may be fetched."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "url must start with http:// or https://"
    host = parsed.hostname
    if not host:
        return "invalid url"
    lowered = host.lower().rstrip(".")
    if lowered in _BLOCKED_HOSTS and not (allow_loopback and lowered == "localhost"):
        return "URL host is not allowed"
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked(ip, allow_loopback=allow_loopback):
            return "URL points to a private or metadata address"
        return None
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, parsed.port or 0, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return None
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked(ip, allow_loopback=allow_loopback):
            return "URL resolves to a private or metadata address"
    return None


def assert_public_url(url: str, *, allow_loopback: bool = False) -> None:
    err = public_url_error(url, allow_loopback=allow_loopback)
    if err:
        raise ValueError(err)
