"""File storage backend (#116) — local filesystem or S3-compatible.

STORAGE_BACKEND=local (default) writes under uploads_dir().
STORAGE_BACKEND=s3 uses boto3 against S3_ENDPOINT / S3_BUCKET.
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


def _s3_client():
    import boto3
    kwargs = {
        "aws_access_key_id": S3_ACCESS_KEY,
        "aws_secret_access_key": S3_SECRET_KEY,
        "region_name": S3_REGION,
    }
    if S3_ENDPOINT:
        kwargs["endpoint_url"] = S3_ENDPOINT
    return boto3.client("s3", **kwargs)


def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Store bytes at `key`; return a fetchable URL/path."""
    key = key.lstrip("/")
    if STORAGE_BACKEND == "s3":
        client = _s3_client()
        client.put_object(
            Bucket=S3_BUCKET, Key=key, Body=data, ContentType=content_type
        )
        if S3_ENDPOINT:
            return f"{S3_ENDPOINT.rstrip('/')}/{S3_BUCKET}/{key}"
        return f"s3://{S3_BUCKET}/{key}"

    dest = uploads_dir() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return f"/uploads/{key}"


def download_file(key: str) -> bytes:
    key = key.lstrip("/")
    if STORAGE_BACKEND == "s3":
        client = _s3_client()
        obj = client.get_object(Bucket=S3_BUCKET, Key=key)
        return obj["Body"].read()
    path = uploads_dir() / key
    if not path.exists():
        # Also try relative to cwd uploads/ for legacy paths
        alt = Path("uploads") / key
        if alt.exists():
            return alt.read_bytes()
        raise FileNotFoundError(key)
    return path.read_bytes()


def get_file_url(key: str, expires: int = 3600) -> str:
    key = key.lstrip("/")
    if STORAGE_BACKEND == "s3":
        client = _s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
    return f"/uploads/{key}"


def storage_ok() -> bool:
    """Health probe — local always ok; s3 tries a HeadBucket."""
    if STORAGE_BACKEND != "s3":
        uploads_dir()
        return True
    try:
        _s3_client().head_bucket(Bucket=S3_BUCKET)
        return True
    except Exception:
        return False
