import re
import os
import fitz  
import pytesseract
from PIL import Image
import pandas as pd
from datetime import datetime

def detect_report_type_from_df_header_row(df: pd.DataFrame, ocr_text: str = None) -> str:
    """
    מזהה את סוג הדו"ח לפי הופעת המילה 'שבת' או 'SAT' בטקסט הגולמי של ה-OCR.
    אם נמצאה — סוג B, אחרת סוג A.
    """
    if ocr_text:
        print("DEBUG: FULL OCR TEXT:")
        print(ocr_text)
        print(f"DEBUG: Checking OCR text for שבת/SAT and common OCR errors...")
        ocr_text_norm = ocr_text.replace(' ', '').replace('\n', '').replace('\r', '')
        patterns = ["שבת", "ש6ת", "ש8ת", "שבת.", "שבת,", "SAT"]
        found = False
        for pat in patterns:
            if pat in ocr_text or pat in ocr_text_norm or pat.upper() in ocr_text.upper():
                print(f"DEBUG: Found pattern '{pat}' in OCR text -> Type A")
                found = True
                break
        if found:
            return "A"
        print("DEBUG: No שבת/SAT or variants in OCR text -> Type B")
        return "B"
    # fallback: old logic
    header_text = " ".join(df.columns.astype(str))
    print(f"DEBUG: Columns: {header_text}")
    if "שבת" in header_text or "SAT" in header_text.upper():
        print("DEBUG: Found שבת/SAT in columns -> Type B")
        return "B"
    for col in df.columns:
        col_data = df[col].astype(str).str.upper()
        print(f"DEBUG: Checking column '{col}' values: {col_data.tolist()[:5]}")
        if col_data.str.contains("שבת").any() or col_data.str.contains("SAT").any():
            print(f"DEBUG: Found שבת/SAT in data of column {col} -> Type B")
            return "B"
    print("DEBUG: No שבת/SAT found in columns or data -> Type A")
    return "A"


def _render_page_to_image(pdf_path: str, page_number: int = 0, zoom: float = 4.0) -> Image.Image:
    """Render a PDF page to a high-resolution PIL Image for OCR."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def preprocess_image(img: Image.Image) -> Image.Image:
    """Grayscale + thresholding to improve OCR accuracy."""
    img = img.convert("L")  # grayscale
    img = img.point(lambda x: 0 if x < 200 else 255, '1')  # threshold
    return img


def _resolve_tesseract_and_lang(preferred_lang: str = 'heb') -> tuple[str, str | None]:
    """
    Ensure Tesseract paths are set and language is available.
    If 'heb' traineddata is missing, fall back to 'eng'.
    Returns (language, tessdata_dir or None).
    """
    # Try common Windows install path if not set
    default_exe = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    if not os.path.isfile(pytesseract.pytesseract.tesseract_cmd):
        if os.path.isfile(default_exe):
            pytesseract.pytesseract.tesseract_cmd = default_exe
    exe_path = pytesseract.pytesseract.tesseract_cmd
    tessdata_dir = None
    if os.path.isfile(exe_path):
        base_dir = os.path.dirname(exe_path)
        candidate = os.path.join(base_dir, 'tessdata')
        if os.path.isdir(candidate):
            tessdata_dir = candidate
            # IMPORTANT: TESSDATA_PREFIX should point to tessdata directory on Windows
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
            # Validate language availability
            heb_file = os.path.join(candidate, 'heb.traineddata')
            if preferred_lang == 'heb' and not os.path.isfile(heb_file):
                return 'eng', tessdata_dir
    return preferred_lang, tessdata_dir


def ocr_pdf_first_page_text(pdf_path: str) -> str:
    """Run OCR on the first page and return the raw text."""
    img = _render_page_to_image(pdf_path)
    img = preprocess_image(img)
    lang, _ = _resolve_tesseract_and_lang('heb')
    lang = (lang + '+eng') if lang == 'heb' else 'eng'
    # Rely on TESSDATA_PREFIX env instead of passing --tessdata-dir to avoid quoting issues on Windows
    text = pytesseract.image_to_string(img, lang=lang)
    return text


def extract_table_from_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Extract attendance tables from the first page of a scanned PDF.
    Returns a DataFrame with date, start, end, hours, and raw OCR line.
    """
    text = ocr_pdf_first_page_text(pdf_path)
    print("==== OCR Text ====")
    print(text)  # בדיקה חזותית

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    print("DEBUG: OCR lines:")
    for line in lines:
        print(line)
    data = []

    date_patterns = [r"\d{4}[\-/]\d{1,2}[\-/]\d{1,2}", r"\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}"]
    # accept HH:MM with optional spaces and unicode colon
    time_pattern = r"(?<!\d)(\d{1,2})\s*[:.：]\s*(\d{2})(?!\d)"
    hours_pattern = r"\d+[\.,]?\d*"

    for line in lines:
        # ניקוי תווים מיוחדים + נרמול טעויות OCR נפוצות
        line_clean = line.replace('\u200e', ' ').replace('\u200f', ' ')
        line_clean = (line_clean
                      .replace('|', ':')
                      .replace('־', '-')
                      .replace('–', '-')
                      .replace('—', '-')
                      .replace('․', '.')
                      .replace('：', ':')
                      .replace('，', ','))
        # map common OCR confusions
        trans_map = str.maketrans({
            'O': '0', 'o': '0',
            'I': '1', 'l': '1', 'ı': '1',
            'S': '5',
            'B': '8',
        })
        line_clean = line_clean.translate(trans_map)
        line_clean = re.sub(r'[^\w\d:.,/\-]', ' ', line_clean)

        # חיפוש תאריך + נרמול
        date_match = None
        for dp in date_patterns:
            m = re.search(dp, line_clean)
            if m:
                date_match = m.group(0)
                break
        # נרמול לפורמט YYYY-MM-DD
        date_norm = None
        if date_match:
            try:
                parts = re.split(r"[\-/]", date_match)
                if len(parts[0]) == 4:
                    y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
                else:
                    d, mo, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y = 2000 + y if y <= 79 else 1900 + y
                dt = datetime(year=y, month=mo, day=d)
                date_norm = dt.strftime("%Y-%m-%d")
            except Exception:
                date_norm = None
        if not date_norm:
            continue

        # חיפוש שעות התחלה/סיום
        matches = re.findall(time_pattern, line_clean)
        times = []
        for h, m in matches:
            h = int(h)
            m = int(m)
            if 0 <= h <= 23 and 0 <= m <= 59:
                times.append(f"{h:02d}:{m:02d}")

        # fallback: compact HHMM (e.g., 0830 1745)
        if len(times) < 2:
            compact = re.findall(r"(?<!\d)(\d{3,4})(?!\d)", line_clean)
            for token in compact:
                if len(token) in (3, 4):
                    h = int(token[:-2])
                    m = int(token[-2:])
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        times.append(f"{h:02d}:{m:02d}")
                if len(times) >= 2:
                    break

        start = times[0] if len(times) >= 1 else ""
        end = times[1] if len(times) >= 2 else ""

        # חיפוש שעות עבודה ישירות
        hours = None
        try:
            after_anchor = end if end else (times[-1] if times else "")
            after = line_clean.split(after_anchor, 1)[1] if after_anchor else ""
            h_m = re.findall(hours_pattern, after)
            if h_m:
                hours = float(h_m[0].replace(',', '.'))
        except Exception:
            hours = None

        # חישוב שעות אם לא נמצאו
        if hours is None or hours == 0:
            if start and end:
                try:
                    fmt = '%H:%M'
                    t0 = datetime.strptime(start, fmt)
                    t1 = datetime.strptime(end, fmt)
                    delta = (t1 - t0).seconds / 3600
                    if delta <= 0:
                        delta += 24
                    hours = round(delta, 2)
                except Exception:
                    hours = 0.0
            else:
                hours = 0.0

        data.append({
            "date": date_norm,
            "start": start,
            "end": end,
            "hours": hours,
            "raw_line": line_clean
        })

    df = pd.DataFrame(data)
    return df


# ---------------- PDF font helpers -----------------
def get_hebrew_font():
    """
    Try to locate and register a Hebrew-capable TTF font for ReportLab.
    Returns (font_name, registered_bool).
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        # Common candidates
        candidates = [
            ("DejaVuSans", r"C:\\Windows\\Fonts\\DejaVuSans.ttf"),
            ("Arial", r"C:\\Windows\\Fonts\\arial.ttf"),
            ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            ("Arial", "/Library/Fonts/Arial.ttf"),
        ]
        for name, path in candidates:
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name, True
            except Exception:
                continue
    except Exception:
        pass
    # Fallback to Helvetica
    return "Helvetica", False


if __name__ == "__main__":
    pdf_file = "input_reports/sample_type_A.pdf"  # שנה לנתיב שלך
    df = extract_table_from_pdf(pdf_file)
    print("==== DataFrame ====")
    print(df)