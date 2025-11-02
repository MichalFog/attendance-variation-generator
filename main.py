import os
import sys
from report_utils import AttendancePDFReader, AttendanceTableExtractor
from rules import AttendanceVariationRules
from report_writer import AttendancePDFWriter

def process_report(input_pdf: str, output_pdf: str):
    print(f"Processing: {input_pdf}")
    reader = AttendancePDFReader(input_pdf)
    first_page_text = reader.extract_text_first_page()
    all_pages_text = reader.extract_text_all_pages()
    
    if not all_pages_text or len(all_pages_text.strip()) < 10:
        print(f"Warning: Extracted text is empty or too short from {input_pdf}")
        print(f"First page text length: {len(first_page_text)}")
        return

    extractor = AttendanceTableExtractor()
    df = extractor.extract_table_from_text(all_pages_text)
    
    if df.empty:
        print(f"Warning: No dates/times found in extracted text from {input_pdf}")
        print(f"Extracted text preview (first 500 chars): {all_pages_text[:500]}")
        return

    print(f"Extracted {len(df)} rows from {input_pdf}")

    report_type = extractor.detect_report_type(all_pages_text)
    header_flags = extractor.detect_columns(first_page_text)

    df_var, _ = AttendanceVariationRules().apply(df, report_type)
    
    if df_var.empty:
        print(f"Warning: DataFrame became empty after applying rules from {input_pdf}")
        return

    writer = AttendancePDFWriter()
    writer.write(df_var, report_type, output_pdf, header_flags)
    print(f"Successfully created: {output_pdf}")

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
