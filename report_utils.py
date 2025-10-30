import os
import pytesseract
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
from datetime import datetime
import re

class AttendancePDFReader:
    """Reads a PDF file and extracts text from its pages using native text first, then OCR fallback."""
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self._configure_tesseract()

    def _configure_tesseract(self):
        tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        if os.path.isfile(tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            tessdata_dir = os.path.join(os.path.dirname(tesseract_cmd), 'tessdata')
            os.environ['TESSDATA_PREFIX'] = tessdata_dir

    def _page_text_or_ocr(self, page_num: int) -> str:
        """Try native text extraction; if empty/garbled, fallback to OCR."""
        doc = fitz.open(self.pdf_path)
        if page_num >= len(doc):
            doc.close(); return ""
        page = doc.load_page(page_num)
        # 1) Native text
        try:
            native_text = page.get_text("text") or ""
        except Exception:
            native_text = ""
        # Heuristic: if native text contains dates/times or has enough alphanum, accept
        if native_text:
            txt = native_text.strip()
            has_date = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", txt)
            has_time = re.search(r"\b\d{1,2}[:.：]\d{2}\b", txt)
            has_words = len(re.findall(r"\w", txt)) > 20
            if has_date or has_time or has_words:
                doc.close()
                return native_text
        # 2) OCR fallback
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            lang = 'heb+eng' if 'heb.traineddata' in os.listdir(os.getenv('TESSDATA_PREFIX', '')) else 'eng'
            ocr_text = pytesseract.image_to_string(img, lang=lang)
        except Exception:
            ocr_text = native_text or ""
        doc.close()
        return ocr_text

    def extract_text_first_page(self) -> str:
        return self._page_text_or_ocr(0)

    def extract_text_all_pages(self) -> str:
        doc = fitz.open(self.pdf_path)
        n = len(doc)
        doc.close()
        return "\n".join(self._page_text_or_ocr(i) for i in range(n))

class AttendanceTableExtractor:
    """Extracts a structured DataFrame from raw OCR/native text."""
    def extract_table_from_text(self, ocr_text: str) -> pd.DataFrame:
        # Parse lines
        all_lines = ocr_text.splitlines()

        # Collect dates with line indices
        date_positions: list[tuple[int, str]] = []
        for i, line in enumerate(all_lines):
            d = self._find_date(line)
            if d:
                date_positions.append((i, d))
        if not date_positions:
            return pd.DataFrame(columns=["date", "start", "end", "hours", "raw_line"])

        # Collect all time tokens in order and detect repetitions
        times_ordered: list[str] = []
        for line in all_lines:
            times = self._find_times(line)
            if times:
                times_ordered.extend(times)

        # Heuristic: if we see long runs of identical times (e.g., many 08:00 then many 15:00)
        # we assume "block mode" where starts are listed as a block followed by ends as a block
        def longest_run(tokens: list[str]) -> int:
            if not tokens: return 0
            best, cur, prev = 1, 1, tokens[0]
            for t in tokens[1:]:
                if t == prev:
                    cur += 1
                    best = max(best, cur)
                else:
                    prev, cur = t, 1
            return best

        num_dates = len(date_positions)
        is_block_mode = longest_run(times_ordered) >= max(3, num_dates // 3)

        rows = []
        if is_block_mode:
            # Block mapping: first N times are starts, next N are ends, optional next N are breaks
            starts = times_ordered[:num_dates]
            ends = times_ordered[num_dates:num_dates * 2]
            breaks = times_ordered[num_dates * 2:num_dates * 3]
            while len(starts) < num_dates: starts.append("")
            while len(ends) < num_dates: ends.append("")
            while len(breaks) < num_dates: breaks.append("")

            for idx, (line_idx, date_str) in enumerate(date_positions):
                start = starts[idx]
                end = ends[idx]
                brk = breaks[idx]
                raw_line = all_lines[line_idx].strip()
                hours = self._find_hours(raw_line, start, end)
                rows.append({
                    "date": date_str,
                    "start": start,
                    "end": end,
                    "break": brk,
                    "hours": hours,
                    "raw_line": raw_line,
                })
            return pd.DataFrame(rows)

        # Per-date window mode: for each date, look until the next date
        for idx, (date_line_idx, date_str) in enumerate(date_positions):
            next_date_idx = date_positions[idx + 1][0] if idx + 1 < num_dates else len(all_lines)
            window_start = max(0, date_line_idx - 5)
            window_end = next_date_idx

            # Collect times in window
            window_times: list[str] = []
            for i in range(window_start, window_end):
                ts = self._find_times(all_lines[i])
                if ts: window_times.extend(ts)

            start = window_times[0] if len(window_times) >= 1 else ""
            end = window_times[1] if len(window_times) >= 2 else ""
            raw_line = all_lines[date_line_idx].strip()
            hours = self._find_hours(raw_line, start, end)
            rows.append({
                "date": date_str,
                "start": start,
                "end": end,
                "hours": hours,
                "raw_line": raw_line,
            })

        return pd.DataFrame(rows)

    @staticmethod
    def _find_date(line: str) -> str | None:
        match = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})', line)
        if not match: return None
        try:
            d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if y < 100: y += 2000
            return datetime(y, m, d).strftime('%Y-%m-%d')
        except ValueError:
            return None

    @staticmethod
    def _find_times(line: str) -> list[str]:
        line = line.translate(str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1', 'S': '5', 'B': '8'}))
        clean = re.sub(r"[^0-9:\./\-\s]", " ", line)
        matches = re.findall(r"\b(\d{1,2})[:.：](\d{2})\b", clean)
        out = [f"{int(h):02d}:{int(m):02d}" for h, m in matches if 0 <= int(h) <= 23 and 0 <= int(m) <= 59]
        potential_times = re.findall(r"(?<![\d/\-])(\d{3,4})(?![\d/\-])", clean)
        for token in potential_times:
            try:
                h, m = (int(token[:2]), int(token[2:])) if len(token) == 4 else (int(token[0]), int(token[1:]))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    formatted = f"{h:02d}:{m:02d}"
                    if formatted not in out: out.append(formatted)
            except ValueError:
                continue
        return sorted(list(set(out)))

    @staticmethod
    def _find_hours(line: str, start: str, end: str) -> float:
        if start and end:
            try:
                t0 = datetime.strptime(start, '%H:%M'); t1 = datetime.strptime(end, '%H:%M')
                delta = (t1 - t0).total_seconds() / 3600
                if delta < 0: delta += 24
                return round(delta, 2)
            except ValueError:
                return 0.0
        return 0.0

    def detect_columns(self, ocr_text: str) -> dict:
        text = (ocr_text or "").replace("\n", " ").lower()
        return {
            "has_shabbat": "שבת" in text or "sat" in text,
            "has_break": "הפסקה" in text or "break" in text,
            "has_notes": "הערות" in text or "notes" in text,
        }

    def detect_report_type(self, text: str) -> str:
        # Structural heuristics: Type A has a long list of dates and separate blocks of repeated times
        lines = text.splitlines()
        # Count dates
        date_count = 0
        times_all: list[str] = []
        for line in lines:
            if self._find_date(line):
                date_count += 1
            ts = self._find_times(line)
            if ts:
                times_all.extend(ts)

        def longest_run(tokens: list[str]) -> int:
            if not tokens:
                return 0
            best, cur, prev = 1, 1, tokens[0]
            for t in tokens[1:]:
                if t == prev:
                    cur += 1
                    best = max(best, cur)
                else:
                    prev, cur = t, 1
            return best

        run = longest_run(times_all)
        # Heuristic thresholds
        if date_count >= 10 and run >= max(3, date_count // 4):
            return 'A'
        return 'B'

def get_hebrew_font():
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        candidates = [
            ("Arial", r"C:\\Windows\\Fonts\\arial.ttf"),
            ("DejaVuSans", r"C:\\Windows\\Fonts\\DejaVuSans.ttf"),
        ]
        for name, path in candidates:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(name, path))
                return name, True
    except Exception:
        pass
    return "Helvetica", False