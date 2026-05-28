"""Server-side PDF generation for invoices using WeasyPrint + Jinja2."""
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")


def render_invoice_pdf(invoice: dict, lines: list, company_name: str, tagline: str = "") -> bytes:
    """Render an invoice as PDF bytes.

    Uses the Jinja2 template at templates/invoice.html.
    WeasyPrint converts the rendered HTML to PDF.
    """
    from weasyprint import HTML  # lazy import — WeasyPrint is slow to import

    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)
    template = env.get_template("invoice.html")
    html_str = template.render(
        invoice=invoice,
        lines=lines,
        company_name=company_name,
        tagline=tagline,
    )
    return HTML(string=html_str).write_pdf()
