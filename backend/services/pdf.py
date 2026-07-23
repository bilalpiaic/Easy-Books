"""Server-side PDF generation using WeasyPrint + Jinja2."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")


def render_html_pdf(template_name: str, context: dict) -> bytes:
    """Render any Jinja2 template under templates/ to PDF bytes."""
    from weasyprint import HTML  # lazy import — WeasyPrint is slow to import

    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)
    template = env.get_template(template_name)
    html_str = template.render(**context)
    return HTML(string=html_str).write_pdf()


def render_invoice_pdf(invoice: dict, lines: list, company_name: str, tagline: str = "") -> bytes:
    """Render an invoice as PDF bytes (back-compat wrapper)."""
    return render_html_pdf(
        "invoice.html",
        {
            "invoice": invoice,
            "lines": lines,
            "company_name": company_name,
            "tagline": tagline,
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
