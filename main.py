

import os
import sys
from report_utils import AttendancePDFReader, AttendanceTableExtractor
from rules import AttendanceVariationRules
from report_writer import AttendancePDFWriter

def process_report(input_pdf: str, output_pdf: str):
    """
    Full processing pipeline for a single report (clean, no debug artifacts).
    """
    # 1. Read all pages from PDF
    reader = AttendancePDFReader(input_pdf)
    first_page_text = reader.extract_text_first_page()
    all_pages_text = reader.extract_text_all_pages()

    # 2. Extract structured data from the text
    extractor = AttendanceTableExtractor()
    df = extractor.extract_table_from_text(all_pages_text)

    # 3. Detect report type and original columns
    report_type = extractor.detect_report_type(all_pages_text)
    header_flags = extractor.detect_columns(first_page_text)

    # 4. Apply variation rules and enrich data
    df_var, _ = AttendanceVariationRules().apply(df, report_type)

    # 5. Write the final report
    writer = AttendancePDFWriter()
    writer.write(df_var, report_type, output_pdf, header_flags)

if __name__ == "__main__":
    input_dir = "input_reports"
    output_dir = "output_reports"

    if len(sys.argv) > 1:
        fname = sys.argv[1]
        in_file = os.path.join(input_dir, fname)
        out_file = os.path.join(output_dir, fname.replace('.pdf', '_variation.pdf'))
        if os.path.exists(in_file):
            process_report(in_file, out_file)
        else:
            print(f"Error: File not found at {in_file}")
    else:
        for fname in os.listdir(input_dir):
            if fname.lower().endswith('.pdf'):
                in_file = os.path.join(input_dir, fname)
                out_file = os.path.join(output_dir, fname.replace('.pdf', '_variation.pdf'))
                process_report(in_file, out_file)
