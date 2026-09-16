"""Dump extracted text per source PDF + a quality report with confidence scores.

Writes:
  data/processed/extracted_text/<pdf-name>.txt   -- full extracted text
    (native PyMuPDF text where available, OCR markdown from
    data/processed/ocr_cache/ where the source PDF is scanned)
  data/processed/REPORT.md                       -- per-file summary

There's no single universal "confidence score" here -- native-text
extraction and OCR are different processes with different failure modes,
so this reports what's actually measurable for each:

  native text  -> self-consistency check (do institution-level seat counts
                  sum to the specialty/region totals also present in the
                  same document?). This directly tests whether extraction
                  got the numbers right, which is what matters for this
                  project -- not a generic OCR-style confidence number.
  OCR          -> docling's own per-page confidence grades (parse/layout/
                  table/ocr scores -> poor/fair/good/excellent), which is
                  the standard signal for that path. Requires re-running
                  via docling's DocumentConverter with confidence reporting
                  enabled (ocr_convert.py currently only dumps markdown) --
                  see the TODO in this file if that's needed later.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from extract_colocados import parse_colocados_pdf, status_and_year
from extract_vagas import parse_vagas_pdf

ROOT = Path(__file__).resolve().parent.parent
RAW_VAGAS = ROOT / "data" / "raw" / "vagas"
RAW_COLOC = ROOT / "data" / "raw" / "colocacoes"
OUT_TEXT = ROOT / "data" / "processed" / "extracted_text"
OCR_CACHE = ROOT / "data" / "processed" / "ocr_cache"
REPORT_PATH = ROOT / "data" / "processed" / "REPORT.md"


def has_native_text(path: Path) -> bool:
    doc = fitz.open(path)
    for i in range(min(5, doc.page_count)):
        if len(doc[i].get_text().strip()) > 50:
            return True
    return False


def dump_native_text(path: Path, out_path: Path) -> int:
    doc = fitz.open(path)
    text = "\n\n".join(f"--- page {i + 1} ---\n{p.get_text()}" for i, p in enumerate(doc))
    out_path.write_text(text, encoding="utf-8")
    return len(text)


def vagas_consistency(rows) -> tuple[int, int]:
    from collections import defaultdict

    inst_sum: dict[str, int] = defaultdict(int)
    specialty_total: dict[str, int] = {}
    for r in rows:
        if r.institution:
            inst_sum[r.specialty] += r.seats
        elif r.region is None:
            specialty_total[r.specialty] = r.seats
    mismatches = sum(
        1 for spec, total in specialty_total.items() if inst_sum.get(spec, 0) != total
    )
    return len(specialty_total), mismatches


def main() -> None:
    OUT_TEXT.mkdir(parents=True, exist_ok=True)
    lines = ["# Extraction quality report", "", "Regenerate with `make report`.", ""]

    lines.append("## vagas/ (seat offers)")
    lines.append("")
    lines.append("| file | year match | method | rows | specialties checked | mismatches |")
    lines.append("|---|---|---|---|---|---|")
    for path in sorted(RAW_VAGAS.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        native = has_native_text(path)
        out_txt = OUT_TEXT / f"{path.stem}.txt"
        if native:
            dump_native_text(path, out_txt)
            method = "native text"
        else:
            ocr_md = OCR_CACHE / f"{path.stem}.md"
            if ocr_md.exists():
                out_txt.write_text(ocr_md.read_text(encoding="utf-8"), encoding="utf-8")
                method = "OCR (docling)"
            else:
                method = "OCR pending"

        try:
            rows = parse_vagas_pdf(str(path), year) if native else []
            n_spec, n_mismatch = vagas_consistency(rows) if rows else (0, 0)
            row_count = len(rows)
        except Exception as e:  # noqa: BLE001 -- report the failure, keep going
            row_count, n_spec, n_mismatch = 0, 0, 0
            method += f" (parse failed: {e})"

        year_in_text = out_txt.exists() and str(year) in out_txt.read_text(encoding="utf-8")
        lines.append(
            f"| {path.name} | {'yes' if year_in_text else 'NO'} | {method} | "
            f"{row_count} | {n_spec} | {n_mismatch} |"
        )

    lines.append("")
    lines.append("## colocacoes/ (placement results)")
    lines.append("")
    lines.append("| file | year match | definitivo | provisorio | method | placements | ordering range |")
    lines.append("|---|---|---|---|---|---|---|")
    for path in sorted(RAW_COLOC.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        native = has_native_text(path)
        out_txt = OUT_TEXT / f"{path.stem}.txt"
        year_match, is_def, is_prov = status_and_year(str(path))

        if native:
            dump_native_text(path, out_txt)
            method = "native text"
        else:
            ocr_md = OCR_CACHE / f"{path.stem}.md"
            if ocr_md.exists():
                out_txt.write_text(ocr_md.read_text(encoding="utf-8"), encoding="utf-8")
                method = "OCR (docling)"
            else:
                method = "OCR pending"

        try:
            rows = parse_colocados_pdf(str(path), year) if native else []
            orderings = [r.ordering_number for r in rows]
            rng = f"{min(orderings)}-{max(orderings)}" if orderings else "n/a"
        except Exception as e:  # noqa: BLE001
            rows, rng = [], "n/a"
            method += f" (parse failed: {e})"

        lines.append(
            f"| {path.name} | {'yes' if year_match else 'NO'} | "
            f"{'yes' if is_def else 'no'} | {'yes' if is_prov else 'no'} | "
            f"{method} | {len(rows)} | {rng} |"
        )

    lines.append("")
    lines.append(
        "Notes: \"mismatches\" (vagas table) counts specialties where the sum "
        "of institution-level seats doesn't equal the specialty's declared "
        "total -- almost all current mismatches trace to \"Medicina Geral e "
        "Familiar\", which nests one indent level deeper than every other "
        "specialty (see backend/extract_vagas.py docstring). "
        "OCR-derived files aren't parsed into rows yet (extract_vagas.py / "
        "extract_colocados.py currently only handle native-text layouts) -- "
        "raw OCR text is dumped for manual review in the meantime."
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
