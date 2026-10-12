from services.display_dates import apply_display_dates, fmt_display_date, fmt_display_datetime


def test_fmt_display_date_iso():
    assert fmt_display_date("2026-06-20") == "20-Jun-26"
    assert fmt_display_date("2026-10-11") == "11-Oct-26"
    assert fmt_display_date("2026-01-01") == "01-Jan-26"


def test_fmt_display_date_datetime_and_idempotent():
    assert fmt_display_date("2026-10-11T14:30:00") == "11-Oct-26"
    assert fmt_display_date("11-Oct-26") == "11-Oct-26"
    assert fmt_display_date("") == ""
    assert fmt_display_date(None) == ""
    assert fmt_display_date("not-a-date") == "not-a-date"


def test_fmt_display_datetime():
    assert fmt_display_datetime("2026-10-11") == "11-Oct-26"
    assert fmt_display_datetime("2026-10-11T14:05:00") == "11-Oct-26 14:05"


def test_apply_display_dates_copies():
    src = {"issue_date": "2026-10-11", "number": "INV-1"}
    out = apply_display_dates(src, ("issue_date", "due_date"))
    assert out["issue_date"] == "11-Oct-26"
    assert src["issue_date"] == "2026-10-11"
    assert out["number"] == "INV-1"


def test_invoice_pdf_html_uses_display_dates():
    from services.pdf import render_template_html

    html = render_template_html(
        "invoice.html",
        {
            "invoice": {
                "number": "INV-1",
                "issue_date": "2026-10-11",
                "due_date": "2026-11-01",
                "customer_name": "Acme",
                "description": "",
                "currency": "PKR",
                "subtotal": 0,
                "gst_amount": 0,
                "gst_rate": 0,
                "total": 0,
            },
            "lines": [],
            "company_name": "Co",
            "tagline": "",
            "logo_url": "",
            "print_fields": [],
            "custom_fields": {},
        },
    )
    assert "11-Oct-26" in html
    assert "01-Nov-26" in html
    assert "2026-10-11" not in html
    assert "2026-11-01" not in html
