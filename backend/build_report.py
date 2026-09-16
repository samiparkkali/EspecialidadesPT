"""Dump extracted text per source PDF + a quality report.

Writes:
  data/processed/extracted_text/<pdf-name>.txt   -- full extracted text
    (native PyMuPDF text where available, OCR markdown from
    data/processed/ocr_cache/ where the source PDF is scanned)
  data/processed/REPORT.md                       -- per-file summary

Row/placement counts are read from the already-generated
data/processed/vagas.csv / colocados.csv (run `make process` first) rather
than re-deriving them here, so this report always reflects whatever the
real pipeline (build_dataset.py, including its extract_vagas_totals.py and
extract_colocados_ocr.py fallbacks) actually produced -- a separate,
simplified re-implementation drifts out of sync with the real one exactly
when it matters most (e.g. this used to show 0 rows for years that the
real pipeline successfully falls back to specialty-totals-only for).

There's no single universal "confidence score" here -- native-text
extraction and OCR are different processes with different failure modes:

  native text  -> self-consistency check (do institution-level seat counts
                  sum to the specialty/region totals also present in the
                  same document?), computed directly against
                  extract_vagas.py's output for years it fully parses.
  OCR          -> not scored the same way (no institution-level rows to
                  sum) -- only the raw placement/total count is reported.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from extract_colocados import status_and_year
from extract_vagas import parse_vagas_pdf

ROOT = Path(__file__).resolve().parent.parent
RAW_VAGAS = ROOT / "data" / "raw" / "vagas"
RAW_COLOC = ROOT / "data" / "raw" / "colocacoes"
OUT_TEXT = ROOT / "data" / "processed" / "extracted_text"
OCR_CACHE = ROOT / "data" / "processed" / "ocr_cache"
VAGAS_CSV = ROOT / "data" / "processed" / "vagas.csv"
COLOCADOS_CSV = ROOT / "data" / "processed" / "colocados.csv"
REPORT_PATH = ROOT / "data" / "processed" / "REPORT.md"


def has_native_text(path: Path) -> bool:
    doc = fitz.open(path)
    sample = min(5, doc.page_count)
    with_text = sum(1 for i in range(sample) if len(doc[i].get_text().strip()) > 50)
    return with_text >= max(2, sample // 2)


def dump_native_text(path: Path, out_path: Path) -> None:
    doc = fitz.open(path)
    text = "\n\n".join(f"--- page {i + 1} ---\n{p.get_text()}" for i, p in enumerate(doc))
    out_path.write_text(text, encoding="utf-8")


def dump_ocr_text(path: Path, out_path: Path) -> bool:
    ocr_md = OCR_CACHE / f"{path.stem}.md"
    if not ocr_md.exists():
        return False
    out_path.write_text(ocr_md.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def vagas_consistency(path: Path, year: int) -> tuple[int, int]:
    """(specialties checked, mismatches) via a fresh full parse -- only
    meaningful for years extract_vagas.py can actually parse; returns
    (0, 0) otherwise (that year's rows in vagas.csv came from the
    specialty-totals fallback instead, nothing to sum-check)."""
    try:
        rows = parse_vagas_pdf(str(path), year)
    except Exception:  # noqa: BLE001
        return 0, 0
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
    vagas_rows = read_csv_rows(VAGAS_CSV)
    colocados_rows = read_csv_rows(COLOCADOS_CSV)

    lines = [
        "# Extraction quality report",
        "",
        "Regenerate with `make report` (run `make process` first so the row",
        "counts below reflect current data).",
        "",
        "## vagas/ (seat offers)",
        "",
        "| file | year match | method | rows | has institution detail | specialties checked | mismatches |",
        "|---|---|---|---|---|---|---|",
    ]

    for path in sorted(RAW_VAGAS.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        native = has_native_text(path)
        out_txt = OUT_TEXT / f"{path.stem}.txt"
        if native:
            dump_native_text(path, out_txt)
            method = "native text"
        elif dump_ocr_text(path, out_txt):
            method = "OCR (docling)"
        else:
            method = "OCR pending"

        year_rows = [r for r in vagas_rows if int(r["year"]) == year]
        has_institution = any(r["institution"] for r in year_rows)
        n_spec, n_mismatch = vagas_consistency(path, year) if native else (0, 0)

        year_in_text = out_txt.exists() and str(year) in out_txt.read_text(encoding="utf-8")
        lines.append(
            f"| {path.name} | {'yes' if year_in_text else 'NO'} | {method} | "
            f"{len(year_rows)} | {'yes' if has_institution else 'no (totals only)'} | "
            f"{n_spec} | {n_mismatch} |"
        )

    lines += [
        "",
        "## colocacoes/ (placement results)",
        "",
        "| file | year match | definitivo | provisorio | method | rows | has institution detail | ordering range |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for path in sorted(RAW_COLOC.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        native = has_native_text(path)
        out_txt = OUT_TEXT / f"{path.stem}.txt"
        ocr_md_path = OCR_CACHE / f"{path.stem}.md"
        year_match, is_def, is_prov = status_and_year(
            str(path), str(ocr_md_path) if ocr_md_path.exists() else None
        )

        if native:
            dump_native_text(path, out_txt)
            method = "native text"
        elif dump_ocr_text(path, out_txt):
            method = "OCR (docling)"
        else:
            method = "OCR pending"

        year_rows = [r for r in colocados_rows if int(r["year"]) == year]
        has_institution = any(r["institution"] for r in year_rows)
        orderings = [int(r["ordering_number"]) for r in year_rows]
        rng = f"{min(orderings)}-{max(orderings)}" if orderings else "n/a"

        lines.append(
            f"| {path.name} | {'yes' if year_match else 'NO'} | "
            f"{'yes' if is_def else 'no'} | {'yes' if is_prov else 'no'} | "
            f"{method} | {len(year_rows)} | {'yes' if has_institution else 'no'} | {rng} |"
        )

    lines += [
        "",
        "Notes: \"mismatches\" (vagas table) counts specialties where the sum "
        "of institution-level seats doesn't equal the specialty's declared "
        "total, for years extract_vagas.py fully parses -- almost all "
        "current mismatches trace to \"Medicina Geral e Familiar\", which "
        "nests one indent level deeper than every other specialty (see "
        "backend/extract_vagas.py's docstring). Years without institution "
        "detail either used extract_vagas_totals.py's \"Total da "
        "Especialidade\"-label fallback (vagas) or "
        "extract_colocados_ocr.py's specialty+ordering-number-only OCR "
        "path (colocacoes) -- see CLAUDE.md and README.md's Known "
        "limitations for which years and why.",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
