"""Parse a colocados/colocacoes-YYYY.pdf (placement results) into rows.

Unlike vagas-*.pdf (indent hierarchy, needs position-based row matching --
see extract_vagas.py), these are plain column tables: Nome, Especialidade,
Instituicao, N. de Cedula, N. de Ordem -- one row per candidate. PyMuPDF's
built-in (rule-based, fast) page.find_tables() handles this cleanly, no
need for a heavy table-structure model.

Per CLAUDE.md's privacy note, the candidate's name and license number
("cedula") are dropped from the output -- only ordering number, specialty,
institution and year are kept, which is what the seat-evolution / cutoff
analysis actually needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class ColocadoRow:
    year: int
    ordering_number: int
    specialty: str
    institution: str


def _clean(cell: str) -> str:
    return re.sub(r"\s+", " ", cell or "").strip()


def parse_colocados_pdf(path: str, year: int) -> list[ColocadoRow]:
    doc = fitz.open(path)
    rows: list[ColocadoRow] = []

    for page in doc:
        text = page.get_text()
        if "Nome" not in text or "Ordem" not in text:
            continue  # cover/intro pages with no data table

        tabs = page.find_tables()
        for table in tabs.tables:
            for record in table.extract():
                if not record or len(record) < 5:
                    continue
                name, specialty, institution, cedula, ordem = record[:5]
                specialty = _clean(specialty)
                institution = _clean(institution)
                ordem = _clean(ordem)
                if specialty == "Especialidade" or not ordem.isdigit():
                    continue  # header row or malformed row
                rows.append(ColocadoRow(year, int(ordem), specialty, institution))

    return rows


def status_and_year(path: str, ocr_fallback_path: str | None = None) -> tuple[bool, bool, bool]:
    """Return (year_matches_filename, is_definitivo, is_provisorio).

    For a scanned PDF, the native PDF text is empty, so pass
    `ocr_fallback_path` (the cached OCR markdown, see ocr_convert.py) to
    check the same thing there instead -- otherwise a scanned file always
    reports "no match" regardless of what it actually says.
    """
    fname_year = re.search(r"20\d\d", path)
    fname_year = fname_year.group(0) if fname_year else None
    doc = fitz.open(path)
    text = "\n".join(doc[i].get_text() for i in range(min(5, doc.page_count)))

    # A scanned PDF can still have a short native-text cover page, so check
    # "not much text" rather than "no text at all" or OCR never triggers.
    if len(text.strip()) < 200 and ocr_fallback_path:
        ocr_path = Path(ocr_fallback_path)
        if ocr_path.exists():
            text = ocr_path.read_text(encoding="utf-8")

    year_match = fname_year is not None and fname_year in text
    is_def = bool(re.search(r"definitiv", text, re.IGNORECASE))
    is_prov = bool(re.search(r"provis", text, re.IGNORECASE))
    return year_match, is_def, is_prov


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/colocacoes/2023-colocados.pdf"
    year = int(re.search(r"20\d\d", path).group(0))

    year_match, is_def, is_prov = status_and_year(path)
    print(f"year_match={year_match} definitivo={is_def} provisorio={is_prov}")

    rows = parse_colocados_pdf(path, year)
    print(f"{len(rows)} placements")
    for r in rows[:10]:
        print(r)

    orderings = [r.ordering_number for r in rows]
    if orderings:
        print(f"ordering_number range: {min(orderings)}..{max(orderings)}")
