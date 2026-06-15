# PyInstaller one-dir spec for the Easy-Books backend.
#
# Build:  cd backend && uv run pyinstaller easybooks-backend.spec
# Output: backend/dist/easybooks-backend/  (run the easybooks-backend[.exe] inside)
#
# The entry point is run_packaged.py, which runs `alembic upgrade head`
# against EB_DATA_DIR's SQLite file and then serves uvicorn on 127.0.0.1:8000.
# Alembic loads env.py + the migration scripts at RUNTIME via importlib, so the
# whole `alembic/` tree (plus alembic.ini) ships as DATA, not as imports.
import os

from PyInstaller.utils.hooks import collect_submodules

# ── Data files (read at runtime, not import-analysed) ───────────────────────
datas = [("alembic.ini", "."), ("alembic", "alembic")]
if os.path.isdir("templates"):          # Jinja2 invoice template for the PDF route
    datas.append(("templates", "templates"))
if os.path.isfile("VERSION"):           # written by prepare-resources before pyinstaller runs
    datas.append(("VERSION", "."))

# ── Hidden imports ──────────────────────────────────────────────────────────
# uvicorn (lifespan/loop/protocol plugins), sqlmodel, the JWT + crypto stacks,
# and our own local packages — routers/services are mounted via explicit imports
# in main.py, but collecting them wholesale guards against any lazy import.
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("sqlmodel")
    + collect_submodules("passlib")
    + collect_submodules("jose")          # python-jose: jwt + backends
    + collect_submodules("alembic")       # config/command + script runtime
    + collect_submodules("routers")
    + collect_submodules("services")
    + collect_submodules("scripts")       # seed_demo + autoseed_demo (first-run demo load)
    + collect_submodules("weasyprint")    # PDF engine (native libs via contrib hook)
    + [
        "models",
        "models_telecom",
        "main",
        "run_packaged",
        "local_config",
        "db",
        "auth",
        "bcrypt",
        "email.mime.multipart",
        "email.mime.text",
        "anyio",
    ]
)

a = Analysis(
    ["run_packaged.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="easybooks-backend",
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, name="easybooks-backend")
