"""Legacy Vercel entry point — prefer `main:app` (see pyproject.toml
`[tool.vercel] entrypoint` and backend/vercel.json).

Kept so older Vercel projects that still route to `api/index.py` keep working.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402,F401
