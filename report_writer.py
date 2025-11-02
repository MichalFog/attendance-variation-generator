from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from bidi.algorithm import get_display
from report_utils import get_hebrew_font
import pandas as pd

class AttendancePDFWriter:
    def write(self, df, report_type, output_path, header_flags):
        if df.empty:
            print("Warning: Received empty data to write. Skipping PDF creation.")
            return

        font_name, _ = get_hebrew_font()
        c = canvas.Canvas(output_path, pagesize=A4)
        page_w, page_h = A4
        margin = 15 * mm
        title = f"דו\"ח נוכחות חודשי – סוג {report_type}"
        
        styles = getSampleStyleSheet()
        rtl_style = ParagraphStyle(
            'RTL',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            alignment=TA_RIGHT
        )
        ltr_style = ParagraphStyle(
            'LTR',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            alignment=TA_LEFT
        )
        
        columns = self._get_columns(df, report_type, header_flags)
        rows = self._build_rows(df, columns)
        
        y = self._draw_table_paginated(c, page_w, page_h, margin, title, columns, rows, rtl_style, ltr_style)
        
        total_hours = sum(float(r.get("hours", 0.0) or 0.0) for r in rows)
        work_days = sum(1 for r in rows if (float(r.get("hours", 0.0) or 0.0)) > 0)
        
        footer_text = f"סה\"כ שעות: {total_hours:.2f} | ימי עבודה: {work_days}"
        footer_fixed = get_display(footer_text)
        footer_para = Paragraph(footer_fixed, rtl_style)
        footer_para.wrapOn(c, page_w - 2*margin, 20)
        footer_para.drawOn(c, margin, y - 10)
        
        c.save()

    def _get_columns(self, df, report_type, header_flags):
        column_map = {
            "date": ("תאריך", 28*mm, "left"),
            "weekday": ("יום בשבוע", 22*mm, "left"),
            "start": ("שעת כניסה", 24*mm, "left"),
            "end": ("שעת יציאה", 24*mm, "left"),
            "hours": ("סה\"כ שעות", 24*mm, "right"),
            "break": ("הפסקה", 20*mm, "left"),
            "notes": ("הערות", 25*mm, "left"),
            "is_sat": ("שבת", 14*mm, "left"),
        }

        desired_keys = list(column_map.keys())

        output_cols = []
        for key in desired_keys:
            include = False
            if key in df.columns:
                include = True
            if header_flags and header_flags.get(key, False):
                include = True
            if key == 'is_sat':
                include = (report_type == 'A')
            if key == 'break' and report_type != 'A':
                include = False
            if include:
                header, width, align = column_map[key]
                output_cols.append((header, width, key, align))
        return output_cols

    def _build_rows(self, df, columns):
        rows = []
        column_keys = [c[2] for c in columns]
        for _, r in df.iterrows():
            row_data = {}
            for key in column_keys:
                value = r.get(key, "")
                row_data[key] = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
            rows.append(row_data)
        return rows

    def _draw_table_paginated(self, c, page_w, page_h, margin, title, col_defs, rows, rtl_style, ltr_style):
        def has_hebrew(text):
            if not text:
                return False
            for char in str(text):
                if '\u0590' <= char <= '\u05FF':
                    return True
            return False
        
        def draw_header(start_y):
            x = margin
            y = start_y
            row_height = 8*mm
            
            title_fixed = get_display(title)
            title_para = Paragraph(title_fixed, rtl_style)
            title_para.wrapOn(c, page_w - 2*margin, row_height)
            title_para.drawOn(c, margin, page_h-margin-2)
            
            c.setFillColor(colors.lightgrey)
            c.rect(x, y-row_height, sum(w for _,w,_,_ in col_defs), row_height, stroke=0, fill=1)
            c.setFillColor(colors.black)
            cx = x
            for t,w,align,_ in col_defs:
                c.rect(cx, y-row_height, w, row_height, stroke=1, fill=0)
                if has_hebrew(t):
                    header_fixed = get_display(str(t))
                    header_para = Paragraph(header_fixed, rtl_style)
                    header_para.wrapOn(c, w-4, row_height)
                    header_para.drawOn(c, cx+2, y-row_height+1)
                else:
                    c.setFont(c._fontname, 10)
                    c.drawString(cx+2, y-row_height+2, str(t))
                cx += w
            return y-row_height

        def draw_text_aligned(x, y, w, text, align):
            if not text:
                return
            text_str = str(text)
            if has_hebrew(text_str):
                text_fixed = get_display(text_str)
                para = Paragraph(text_fixed, rtl_style)
                para.wrapOn(c, w-4, 8*mm)
                para.drawOn(c, x+2, y)
            else:
                c.setFont(c._fontname, 10)
                if align == "right":
                    tw = c.stringWidth(text_str, c._fontname, 10)
                    c.drawString(x+w-2-tw, y, text_str)
                else:
                    c.drawString(x+2, y, text_str)

        row_height = 8*mm
        usable_bottom = margin+24
        y = draw_header(page_h-margin-12*mm)

        for r in rows:
            if y-row_height < usable_bottom:
                c.showPage()
                y = draw_header(page_h-margin-12*mm)
            
            cx = margin
            for _,width,key,align in col_defs:
                c.rect(cx, y-row_height, width, row_height, stroke=1, fill=0)
                val = r.get(key, "")
                text = f"{float(val):.2f}" if (key == "hours" and val) else str(val)
                draw_text_aligned(cx, y-row_height+2, width, text, align)
                cx += width
            y -= row_height
        return y
