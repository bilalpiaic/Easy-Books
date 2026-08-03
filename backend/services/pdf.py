"""Server-side PDF generation using WeasyPrint + Jinja2."""
from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, TemplateError

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


def _import_weasyprint_html():
    """Lazy-import WeasyPrint HTML; raise PdfEngineError with actionable detail."""
    try:
        from weasyprint import HTML  # slow + needs native Pango/Cairo
        return HTML
    except Exception as e:
        detail = f"{type(e).__name__}: {e}".strip()
        if len(detail) > 280:
            detail = detail[:277] + "…"
        apt = " ".join(WEASYPRINT_APT_PACKAGES)
        raise PdfEngineError(
            f"{_PDF_UNAVAILABLE} (import failed: {detail}). "
            f"On Debian/Ubuntu/WSL: sudo apt-get install -y {apt}"
        ) from e


def render_template_html(template_name: str, context: dict) -> str:
    """Render a Jinja2 template under templates/ to an HTML string."""
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)
    return env.get_template(template_name).render(**context)


def render_html_pdf(template_name: str, context: dict) -> bytes:
    """Render any Jinja2 template under templates/ to PDF bytes."""
    HTML = _import_weasyprint_html()

    try:
        html_str = render_template_html(template_name, context)
    except TemplateError as e:
        raise PdfRenderError(
            f"PDF template error ({template_name}): {type(e).__name__}: {e}"
        ) from e

    try:
        return HTML(string=html_str).write_pdf()
    except Exception as e:
        detail = f"{type(e).__name__}: {e}".strip()
        if len(detail) > 280:
            detail = detail[:277] + "…"
        raise PdfEngineError(f"{_PDF_UNAVAILABLE} ({detail})") from e


def render_invoice_pdf(
    invoice: dict,
    lines: list,
    company_name: str,
    tagline: str = "",
    logo_url: str = "",
) -> bytes:
    """Render an invoice as PDF bytes (back-compat wrapper)."""
    return render_html_pdf(
        "invoice.html",
        {
            "invoice": invoice,
            "lines": lines,
            "company_name": company_name,
            "tagline": tagline,
            "logo_url": logo_url,
        },
    )


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


def render_bill_pdf(bill: dict, lines: list, company_name: str, tagline: str = "") -> bytes:
    """Render a vendor bill as PDF bytes."""
    return render_html_pdf(
        "bill.html",
        {
            "bill": bill,
            "lines": lines,
            "company_name": company_name,
            "tagline": tagline,
        },
    )
