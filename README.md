# Attendance Variation – PDF in/PDF out

## Prerequisites
- Python 3.10+
- Tesseract OCR with Hebrew data
  - Windows: download and install from `https://github.com/UB-Mannheim/tesseract/wiki`
    - Default path used by the code: `C:\Program Files\Tesseract-OCR\tesseract.exe`
    - During install, include Hebrew language (heb)
  - macOS: `brew install tesseract tesseract-lang`
  - Linux (Debian/Ubuntu): `sudo apt-get install tesseract-ocr tesseract-ocr-heb`

## Install
```bash
pip install -r requirements.txt
```

## Run
Process all PDFs in `input_reports`:
```bash
python main.py
```
Process a single file:
```bash
python main.py sample_type_A.pdf
```
Outputs are written to `output_reports` as `<name>_variation.pdf` only (no CSV/TXT artifacts).

## What it does
- Reads the original PDF (native text first, OCR fallback) across all pages
- Extracts the attendance table and applies minimal, deterministic validation rules
  - Preserves extracted `start`/`end`/`hours` when sensible; fixes only invalid rows
- Detects report type by structure (A/B)
  - Type A: many dates + blocks of repeated times
- Generates a new PDF that mirrors the original layout order with the varied data
  - Columns shown by type:
    - Type A: date, weekday, start, end, hours, break, שבת
    - Type B: date, weekday, start, end, hours (no break, no שבת)

## Project structure
```
├── main.py            # Orchestration (read → extract → rules → write)
├── report_utils.py    # AttendancePDFReader (PDF/OCR), AttendanceTableExtractor (parsing)
├── rules.py           # AttendanceVariationRules (minimal corrections, weekday/שבת)
├── report_writer.py   # AttendancePDFWriter (pagination, dynamic columns, totals)
├── input_reports/     # Source PDFs
└── output_reports/    # Result PDFs
```

## Troubleshooting
- Tesseract not found on Windows: verify `C:\Program Files\Tesseract-OCR\tesseract.exe`. If installed elsewhere, update the path in `report_utils.py`.
- Hebrew glyphs missing in output: ensure a Hebrew-capable font exists (the code tries `Arial` then `DejaVuSans`).
