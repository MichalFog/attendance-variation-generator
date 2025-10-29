

import os
from report_utils import detect_report_type_from_df_header_row, extract_table_from_pdf
from rules import apply_rules
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

from report_utils import ocr_pdf_first_page_text, get_hebrew_font

def process_report(input_pdf, output_pdf):
    ocr_text = ocr_pdf_first_page_text(input_pdf)
    df = extract_table_from_pdf(input_pdf)
    report_type = detect_report_type_from_df_header_row(df, ocr_text)
    header_flags = _detect_header_features(ocr_text)
    print(f"File: {input_pdf} | Detected report type: {report_type}")
    print("Original data:")
    print(df.head())
    new_df, log = apply_rules(df, report_type)
    create_pdf_report(new_df, report_type, output_pdf, header_flags)

def _draw_table_paginated(c, page_w, page_h, margin, title, col_defs, rows):
    """Draw a table across pages if needed.
    col_defs = [(title, width_mm, key, align)] where align in {"left","right"}
    """
    def draw_header(start_y):
        x = margin
        y = start_y
        row_height = 8 * mm
        c.setFont(c._fontname, 10)
        c.drawString(margin, page_h - margin, title)
        c.setFillColor(colors.lightgrey)
        c.rect(x, y - row_height, sum(w for _, w, _, _ in col_defs), row_height, stroke=0, fill=1)
        c.setFillColor(colors.black)
        cx = x
        for t, w, _, _ in col_defs:
            c.rect(cx, y - row_height, w, row_height, stroke=1, fill=0)
            c.drawString(cx + 2, y - row_height + 2, t)
            cx += w
        return y - row_height

    def draw_text_aligned(x, y, w, text, align):
        if align == "right":
            # crude right alignment approximation
            text_width = c.stringWidth(text, c._fontname, 10)
            c.drawString(x + w - 2 - text_width, y, text)
        else:
            c.drawString(x + 2, y, text)

    row_height = 8 * mm
    usable_bottom = margin + 24
    y = draw_header(page_h - margin - 12 * mm)

    for r in rows:
        # New page if needed
        if y - row_height < usable_bottom:
            c.showPage()
            c.setFont(c._fontname, 10)
            y = draw_header(page_h - margin - 12 * mm)

        cx = margin
        for _, width, key, align in col_defs:
            c.rect(cx, y - row_height, width, row_height, stroke=1, fill=0)
            val = r.get(key, "")
            text = f"{val:.2f}" if isinstance(val, float) else str(val)
            draw_text_aligned(cx, y - row_height + 2, width, text, align)
            cx += width
        y -= row_height
    return y


def _get_columns_for_type(report_type, header_flags):
    cols = [
        ("תאריך", 28 * mm, "date", "left"),
        ("יום בשבוע", 22 * mm, "weekday", "left"),
        ("שעת כניסה", 24 * mm, "start", "left"),
        ("שעת יציאה", 24 * mm, "end", "left"),
    ]
    if header_flags.get("has_break"):
        cols.append(("הפסקה", 20 * mm, "break", "left"))
    cols.append(("סה\"כ שעות", 24 * mm, "hours", "right"))
    if header_flags.get("has_notes"):
        cols.append(("הערות", 25 * mm, "notes", "left"))
    if header_flags.get("has_shabbat"):
        cols.append(("שבת", 14 * mm, "is_sat", "left"))
    return cols


def _hebrew_weekday_from_iso(date_text: str) -> str:
    """Convert YYYY-MM-DD to Hebrew weekday name used in source docs."""
    try:
        from datetime import datetime
        y, m, d = [int(x) for x in date_text.split('-')]
        wd = datetime(y, m, d).weekday()  # 0=Mon .. 6=Sun
        # Source shows Sunday first ("ראשון") for 1/1/23 → Sunday
        names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        return names[wd]
    except Exception:
        return ""


def _build_rows_from_df(df, report_type, header_flags):
    rows = []
    for _, r in df.iterrows():
        date_iso = r.get("date", "")
        row = {
            "date": date_iso,
            "weekday": _hebrew_weekday_from_iso(date_iso),
            "start": r.get("start", ""),
            "end": r.get("end", ""),
            "hours": r.get("hours", 0.0),
            "notes": "",
        }
        # Optional: break column if schema requires
        if header_flags.get("has_break"):
            try:
                h = float(r.get("hours", 0.0) or 0.0)
            except Exception:
                h = 0.0
            row["break"] = "00:30" if h >= 6.0 else ""
        # Optional: שבת column
        if header_flags.get("has_shabbat"):
            row["is_sat"] = "כן" if row.get("weekday") == "שבת" or "שבת" in str(r.get("raw_line", "")) else ""
        rows.append(row)
    return rows


def _detect_header_features(ocr_text: str) -> dict:
    text = (ocr_text or "").replace("\n", " ")
    text_norm = text.replace(" ", "")
    flags = {
        "has_shabbat": ("שבת" in text) or ("שבת" in text_norm) or ("SAT" in text.upper()),
        "has_break": ("הפסק" in text) or ("הפסקה" in text),
        "has_notes": ("הערות" in text) or ("הערה" in text),
    }
    return flags


def _compute_totals(rows):
    total_hours = sum(float(r.get("hours", 0.0)) for r in rows)
    work_days = sum(1 for r in rows if (r.get("hours") or 0) > 0)
    return total_hours, work_days


def create_pdf_report(df, report_type, output_path, header_flags=None):
    header_flags = header_flags or {}
    c = canvas.Canvas(output_path, pagesize=A4)
    font_name, _ = get_hebrew_font()
    c.setFont(font_name, 10)

    page_w, page_h = A4
    margin = 15 * mm

    title = f"דו\"ח נוכחות חודשי – סוג {report_type}"

    columns = _get_columns_for_type(report_type, header_flags)
    rows = _build_rows_from_df(df, report_type, header_flags)
    y = _draw_table_paginated(c, page_w, page_h, margin, title, columns, rows)

    # Totals footer
    total_hours, work_days = _compute_totals(rows)
    c.setFont(font_name, 10)
    c.drawString(margin, y - 10, f"סה\"כ שעות: {total_hours:.2f}  |  ימי עבודה: {work_days}")

    c.save()

if __name__ == "__main__":
    import sys
    input_dir = "input_reports"
    output_dir = "output_reports"
    if len(sys.argv) > 1:
        fname = sys.argv[1]
        input_pdf = os.path.join(input_dir, fname)
        output_pdf = os.path.join(output_dir, fname.replace('.pdf', '_variation.pdf'))
        if not os.path.isfile(input_pdf):
            print(f"File not found: {input_pdf}")
        else:
            process_report(input_pdf, output_pdf)
    else:
        for fname in os.listdir(input_dir):
            if fname.lower().endswith('.pdf'):
                input_pdf = os.path.join(input_dir, fname)
                output_pdf = os.path.join(output_dir, fname.replace('.pdf', '_variation.pdf'))
                process_report(input_pdf, output_pdf)
