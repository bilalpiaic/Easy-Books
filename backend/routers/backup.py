"""Local backup/restore of the SQLite database + uploads (admin only).

Only available on SQLite installs (on-premise). On Postgres this 400s — cloud
backups are the platform's responsibility.
"""
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from db import engine
from local_config import data_dir, sqlite_path, uploads_dir
from routers.common import AdminUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _require_sqlite():
    if engine.url.get_backend_name() != "sqlite":
        raise HTTPException(400, "Backup/restore is only available on local SQLite installs.")


@router.get("/download")
def download_backup(user: AdminUserDep):
    """Stream a zip of the SQLite database + uploads."""
    _require_sqlite()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        db_path = Path(sqlite_path())
        if db_path.exists():
            z.write(db_path, "database.db")
        up = uploads_dir()
        for f in up.rglob("*"):
            if f.is_file():
                z.write(f, str(Path("uploads") / f.relative_to(up)))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="easybooks-backup.zip"'},
    )


@router.post("/restore")
def restore_backup(session: SessionDep, user: AdminUserDep, file: UploadFile = File(...)):
    """Restore the database + uploads from a backup zip. Keeps a .db.bak safety
    copy. The app must be restarted to rebind the engine to the new file."""
    _require_sqlite()
    raw = file.file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Uploaded file is not a valid backup zip.")
    names = zf.namelist()
    if "database.db" not in names:
        raise HTTPException(400, "Backup is missing database.db.")

    base = data_dir().resolve()

    def _safe_target(name: str) -> Path:
        """Resolve an entry to a path guaranteed to stay inside the data dir
        (Zip Slip guard). Rejects absolute paths and `..` traversal."""
        if name.startswith("/") or ".." in Path(name).parts:
            raise HTTPException(400, "Backup contains an unsafe path.")
        target = (base / name).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise HTTPException(400, "Backup contains an unsafe path.")
        return target

    # Validate every entry up-front before writing anything.
    entries = [n for n in names if not n.endswith("/")]
    safe = {n: _safe_target(n) for n in entries
            if n == "database.db" or n.startswith("uploads/")}

    db_path = Path(sqlite_path())
    if db_path.exists():
        db_path.replace(db_path.with_suffix(".db.bak"))
    safe["database.db"].write_bytes(zf.read("database.db"))
    for n, target in safe.items():
        if n.startswith("uploads/"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(n))

    log_audit(session, user, "RESTORE", "backup", None, {"file": file.filename})
    session.commit()
    return {"restored": True, "note": "Restart the app to load the restored database."}
