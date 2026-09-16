"""Convert a scanned (image-only) PDF to markdown via docling + RapidOCR.

Only used for source PDFs that have no extractable native text (checked by
extract.detect_needs_ocr). Table-structure detection is disabled -- it's the
slow part and we re-parse rows from the OCR'd text ourselves, the same way
extract.py parses native-text PDFs.

Usage: python ocr_convert.py <input.pdf> <output.md>
"""

import sys

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def convert(input_path: str, output_path: str) -> None:
    opts = PdfPipelineOptions()
    opts.do_ocr = True
    opts.do_table_structure = False

    conv = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    result = conv.convert(input_path)
    markdown = result.document.export_to_markdown()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"wrote {len(markdown)} chars to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python ocr_convert.py <input.pdf> <output.md>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
