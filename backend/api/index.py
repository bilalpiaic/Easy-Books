"""Vercel serverless entry point for the FastAPI app.

Vercel's @vercel/python runtime imports `app` (or `handler`) from this file
and forwards every HTTP request through ASGI. The actual FastAPI app lives
in `backend/main.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402,F401
