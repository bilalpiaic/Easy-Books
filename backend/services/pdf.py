"""Server-side PDF generation using WeasyPrint + Jinja2."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")


def render_template_html(template_name: str, context: dict) -> str:
    """Render a Jinja2 template under templates/ to an HTML string."""
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)
    return env.get_template(template_name).render(**context)


def render_html_pdf(template_name: str, context: dict) -> bytes:
    """Render any Jinja2 template under templates/ to PDF bytes."""
    from weasyprint import HTML  # lazy import — WeasyPrint is slow to import

    html_str = render_template_html(template_name, context)
    return HTML(string=html_str).write_pdf()


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
