"""File storage backend (#116 / #426) — local filesystem or S3-compatible.

STORAGE_BACKEND=local (default) writes under uploads_dir().
STORAGE_BACKEND=s3 uses boto3 against S3_ENDPOINT / S3_BUCKET.

Keys: tenants/{tenant_id}/{kind}/{filename}. App-facing URLs are always
authenticated `/api/files/{key}` paths (#418). Never public `/uploads/`.
Supabase remains a read fallback until scripts.migrate_storage has copied
existing objects.
"""
from __future__ import annotations

import os
from pathlib import Path

from local_config import uploads_dir

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_REGION = os.environ.get("S3_REGION", "auto")

OBJECT_KINDS = frozenset({"logo", "avatar", "attachment", "pdf"})

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"


def sniff_image(data: bytes) -> tuple[str, str]:
    """Return (extension-with-dot, mime) from magic bytes. Reject SVG/HTML."""
    sample = data[:64]
    if not data:
        raise ValueError("empty file")
    lowered = data[:256].lstrip().lower()
    if lowered.startswith(b"<svg") or b"<svg" in lowered or lowered.startswith(b"<?xml"):
        raise ValueError("SVG is not allowed")
    if lowered.startswith(b"<") or b"<html" in lowered or b"<!doctype" in lowered:
        raise ValueError("HTML is not allowed")
    if data.startswith(_PNG):
        return ".png", "image/png"
    if data.startswith(_JPEG):
        return ".jpg", "image/jpeg"
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        return ".gif", "image/gif"
    if sample[:4] == b"RIFF" and sample[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise ValueError("unrecognized image type")


def object_key(tenant_id: int, kind: str, filename: str) -> str:
    """Canonical object key: tenants/{tenant_id}/{kind}/{filename}."""
    kind = (kind or "").strip().lower()
    if kind not in OBJECT_KINDS:
        raise ValueError(f"unknown storage kind {kind!r}")
    name = Path(str(filename)).name
    if not name or name in (".", ".."):
        raise ValueError("invalid object name")
    return f"tenants/{int(tenant_id)}/{kind}/{name}"


def local_file_url(key: str) -> str:
    """Authenticated fetch path. Never a public /uploads URL."""
    return f"/api/files/{key.lstrip('/')}"


def key_from_file_url(url: str | None) -> str | None:
    if not url:
        return None
    prefix = "/api/files/"
    if url.startswith(prefix):
        return url[len(prefix):].split("?", 1)[0].lstrip("/")
    return None


def _s3_client():
    import boto3
    kwargs = {
        "aws_access_key_id": S3_ACCESS_KEY or os.environ.get("S3_ACCESS_KEY", ""),
        "aws_secret_access_key": S3_SECRET_KEY or os.environ.get("S3_SECRET_KEY", ""),
        "region_name": os.environ.get("S3_REGION", S3_REGION) or "auto",
    }
    endpoint = os.environ.get("S3_ENDPOINT", S3_ENDPOINT)
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _backend() -> str:
    return (os.environ.get("STORAGE_BACKEND") or STORAGE_BACKEND or "local").strip().lower()


def _bucket() -> str:
    return os.environ.get("S3_BUCKET", S3_BUCKET)


def _local_path(key: str) -> Path:
    return uploads_dir() / key


def _local_get(key: str) -> bytes:
    path = _local_path(key)
    if path.exists() and path.is_file():
        return path.read_bytes()
    alt = Path("uploads") / key
    if alt.exists() and alt.is_file():
        return alt.read_bytes()
    raise FileNotFoundError(key)


def _s3_get(key: str) -> bytes:
    from botocore.exceptions import ClientError

    client = _s3_client()
    try:
        obj = client.get_object(Bucket=_bucket(), Key=key)
        return obj["Body"].read()
    except ClientError as exc:
        code = (exc.response or {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            raise FileNotFoundError(key) from exc
        raise


def _supabase_get(key: str) -> bytes:
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    service_key = (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()
    bucket = (os.environ.get("SUPABASE_BUCKET") or "attachments").strip() or "attachments"
    if not url or not service_key:
        raise FileNotFoundError(key)
    try:
        from supabase import create_client
        data = create_client(url, service_key).storage.from_(bucket).download(key)
    except Exception as exc:
        raise FileNotFoundError(key) from exc
    if not data:
        raise FileNotFoundError(key)
    return data if isinstance(data, (bytes, bytearray)) else bytes(data)


def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Store bytes at `key`; return an authenticated `/api/files/{key}` path."""
    key = key.lstrip("/")
    if _backend() == "s3":
        client = _s3_client()
        client.put_object(
            Bucket=_bucket(), Key=key, Body=data, ContentType=content_type
        )
        return local_file_url(key)

    dest = _local_path(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return local_file_url(key)


def download_file(key: str) -> bytes:
    """Read an object. S3 miss falls through to local leftover, then Supabase."""
    key = key.lstrip("/")
    if _backend() == "s3":
        try:
            return _s3_get(key)
        except FileNotFoundError:
            pass
        try:
            return _local_get(key)
        except FileNotFoundError:
            pass
        return _supabase_get(key)
    try:
        return _local_get(key)
    except FileNotFoundError:
        return _supabase_get(key)


def delete_file(key: str) -> None:
    """Best-effort delete from the active backend (and local leftover)."""
    key = key.lstrip("/")
    if _backend() == "s3":
        try:
            _s3_client().delete_object(Bucket=_bucket(), Key=key)
        except Exception:
            pass
    path = _local_path(key)
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def get_file_url(key: str, expires: int = 3600) -> str:
    key = key.lstrip("/")
    if _backend() == "s3":
        client = _s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": _bucket(), "Key": key},
            ExpiresIn=expires,
        )
    return local_file_url(key)


def storage_ok() -> bool:
    """Health probe — local always ok; s3 tries a HeadBucket.

    Must not be used as a Docker/K8s liveness probe (#427).
    """
    if _backend() != "s3":
        uploads_dir()
        return True
    try:
        _s3_client().head_bucket(Bucket=_bucket())
        return True
    except Exception:
        return False
