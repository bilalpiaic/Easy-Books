"""Server-side PDF generation using WeasyPrint + Jinja2."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateNotFound

_TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")

_PDF_UNAVAILABLE = (
    "PDF engine unavailable. Install WeasyPrint system libraries "
    "(Pango/Cairo) or check the backend log, then try again."
)

# Debian/Ubuntu (incl. WSL2) packages required for `from weasyprint import HTML`.
WEASYPRINT_APT_PACKAGES = (
    "libcairo2",
    "libpango-1.0-0",
    "libpangocairo-1.0-0",
    "libgdk-pixbuf-2.0-0",
    "libffi8",
    "shared-mime-info",
    "fonts-dejavu-core",
)

# Prefer tschoonj's GTK3 runtime (WeasyPrint docs) over older winget GtkD builds.
_WINDOWS_GTK_BIN_CANDIDATES = (
    os.environ.get("GTK_BIN") or "",
    os.environ.get("WEASYPRINT_DLL_DIRECTORIES") or "",  # pathsep-separated ok
    r"C:\Program Files\GTK3-Runtime Win64\bin",
    r"C:\GTK3-Runtime Win64\bin",
    r"C:\Program Files\Gtk-Runtime\bin",
    r"C:\Program Files (x86)\Gtk-Runtime\bin",
)


class PdfEngineError(Exception):
    """WeasyPrint / system library failure — map to HTTP 503 at the edge."""

    def __init__(self, message: str = _PDF_UNAVAILABLE):
        super().__init__(message)
        self.message = message


class PdfRenderError(Exception):
    """Template/data failure while building a PDF — map to HTTP 500."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def pdf_http(exc: Exception) -> HTTPException:
    """Convert PDF failures to an HTTP error (503 engine / 500 render)."""
    if isinstance(exc, PdfEngineError):
        return HTTPException(503, exc.message)
    if isinstance(exc, PdfRenderError):
        return HTTPException(500, exc.message)
    return HTTPException(503, _PDF_UNAVAILABLE)


def _windows_gtk_bins() -> list[Path]:
    """Resolve existing GTK runtime bin directories on Windows."""
    found: list[Path] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        for part in raw.replace(",", os.pathsep).split(os.pathsep):
            part = part.strip().strip('"')
            if not part:
                continue
            p = Path(part)
            # Allow pointing at the install root instead of bin/
            if p.is_dir() and not (p / "libgobject-2.0-0.dll").exists():
                maybe = p / "bin"
                if (maybe / "libgobject-2.0-0.dll").exists():
                    p = maybe
            key = str(p).lower()
            if key in seen:
                continue
            if p.is_dir() and (p / "libgobject-2.0-0.dll").exists():
                seen.add(key)
                found.append(p)

    for raw in _WINDOWS_GTK_BIN_CANDIDATES:
        if raw:
            _add(raw)

    # Also scan PATH for a bin that already contains gobject.
    for part in os.environ.get("PATH", "").split(os.pathsep):
        _add(part)

    return found


def _prepare_native_libs() -> None:
    """Make Pango/Cairo/GObject loadable before importing WeasyPrint.

    On Windows (Python 3.8+), DLL dependencies are *not* resolved from PATH
    alone — callers must ``os.add_dll_directory`` the GTK Runtime ``bin``
    folder or ``cffi.dlopen`` fails with ``error 0x7e`` even when the DLL
    is present. Prefer a single bin directory (newest first) so an older
    winget GtkD install cannot shadow tschoonj's newer Pango.
    """
    if sys.platform != "win32":
        return

    bins = _windows_gtk_bins()
    if not bins:
        return

    # Only the highest-priority match — mixing two GTK trees breaks symbol lookup.
    bin_dir = bins[0]
    path_str = str(bin_dir)
    # Prepend so PATH-based loaders also see this tree first.
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p and p.lower() != path_str.lower()]
    os.environ["PATH"] = os.pathsep.join([path_str, *parts])
    os.environ["GTK_BIN"] = path_str
    add = getattr(os, "add_dll_directory", None)
    if add is not None:
        try:
            add(path_str)
        except OSError:
            pass


def _import_hint(exc: BaseException) -> str:
    detail = f"{type(exc).__name__}: {exc}".strip()
    if len(detail) > 280:
        detail = detail[:277] + "…"
    if sys.platform == "win32":
        return (
            f"{_PDF_UNAVAILABLE} (import failed: {detail}). "
            "On Windows install the WeasyPrint GTK3 runtime "
            "(https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases), "
            "then restart the backend. install-and-run.ps1 installs it automatically."
        )
    apt = " ".join(WEASYPRINT_APT_PACKAGES)
    return (
        f"{_PDF_UNAVAILABLE} (import failed: {detail}). "
        f"On Debian/Ubuntu/WSL: sudo apt-get install -y {apt}"
    )


def _import_weasyprint_html():
    """Lazy-import WeasyPrint HTML; raise PdfEngineError with actionable detail."""
    _prepare_native_libs()
    try:
        from weasyprint import HTML  # slow + needs native Pango/Cairo
        return HTML
    except Exception as e:
        raise PdfEngineError(_import_hint(e)) from e


def render_template_html(template_name: str, context: dict) -> str:
    """Render a Jinja2 template under templates/ to an HTML string."""
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)
    return env.get_template(template_name).render(**context)


def _html_to_pdf(html_str: str) -> bytes:
    HTML = _import_weasyprint_html()
    try:
        return HTML(string=html_str).write_pdf()
    except Exception as e:
        detail = f"{type(e).__name__}: {e}".strip()
        if len(detail) > 280:
            detail = detail[:277] + "…"
        raise PdfEngineError(f"{_PDF_UNAVAILABLE} ({detail})") from e


def render_html_pdf(template_name: str, context: dict) -> bytes:
    """Render any Jinja2 template under templates/ to PDF bytes."""
    try:
        html_str = render_template_html(template_name, context)
    except TemplateError as e:
        raise PdfRenderError(
            f"PDF template error ({template_name}): {type(e).__name__}: {e}"
        ) from e
    return _html_to_pdf(html_str)


def render_html_string_pdf(html_source: str, context: dict) -> bytes:
    """Render a tenant clone string through the sandboxed Jinja env, then PDF."""
    from services.print_templates import render_sandboxed_html

    try:
        html_str = render_sandboxed_html(html_source, context)
    except TemplateNotFound as e:
        raise PdfRenderError(
            f"PDF template include is not allowed: {type(e).__name__}: {e}"
        ) from e
    except TemplateError as e:
        raise PdfRenderError(
            f"PDF template error: {type(e).__name__}: {e}"
        ) from e
    return _html_to_pdf(html_str)


def render_invoice_pdf(
    invoice: dict,
    lines: list,
    company_name: str,
    tagline: str = "",
    logo_url: str = "",
    html: str | None = None,
    print_fields: list | None = None,
    custom_fields: dict | None = None,
) -> bytes:
    """Render an invoice as PDF bytes (back-compat wrapper)."""
    ctx = {
        "invoice": invoice,
        "lines": lines,
        "company_name": company_name,
        "tagline": tagline,
        "logo_url": logo_url,
        "print_fields": print_fields or [],
        "custom_fields": custom_fields if custom_fields is not None else (invoice.get("custom_fields") or {}),
    }
    if html:
        return render_html_string_pdf(html, ctx)
    return render_html_pdf("invoice.html", ctx)


def render_lab_report_pdf(report: dict, company_name: str, tagline: str = "") -> bytes:
    """Render a laboratory test report as PDF bytes."""
    return render_html_pdf(
        "lab_report.html",
        {
            "report": report,
            "company_name": company_name,
            "tagline": tagline,
        },
    )


def render_bill_pdf(
    bill: dict,
    lines: list,
    company_name: str,
    tagline: str = "",
    html: str | None = None,
    print_fields: list | None = None,
    custom_fields: dict | None = None,
) -> bytes:
    """Render a vendor bill as PDF bytes."""
    ctx = {
        "bill": bill,
        "lines": lines,
        "company_name": company_name,
        "tagline": tagline,
        "print_fields": print_fields or [],
        "custom_fields": custom_fields if custom_fields is not None else (bill.get("custom_fields") or {}),
    }
    if html:
        return render_html_string_pdf(html, ctx)
    return render_html_pdf("bill.html", ctx)
