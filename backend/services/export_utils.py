"""Shared export helpers: formula-injection sanitizer + streaming CSV/XLSX."""
import csv
import io
from typing import Sequence

from fastapi.responses import StreamingResponse


def safe_cell(v) -> str:
    """Neutralise CSV/spreadsheet formula injection.

    A cell value that starts with a formula trigger character (=, +, -, @,
    tab, carriage-return) would be executed when the file is opened in
    Excel / Google Sheets. Prefixing with a single quote forces literal text.
    """
    s = "" if v is None else str(v)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def stream_csv(rows: Sequence[dict], headers: list[str], filename: str) -> StreamingResponse:
    """Return a StreamingResponse for a CSV download."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for row in rows:
        w.writerow([safe_cell(row.get(h, "")) for h in headers])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def stream_xlsx(rows: Sequence[dict], headers: list[str], filename: str) -> StreamingResponse:
    """Return a StreamingResponse for an XLSX download (openpyxl)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append([safe_cell(row.get(h, "")) for h in headers])
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
