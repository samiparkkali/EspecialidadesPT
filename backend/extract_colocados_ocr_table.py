"""Full-row (name/specialty/institution/ordering number) extraction for
colocados OCR markdown produced WITH docling's table-structure detection
enabled (see backend/ocr_convert.py's do_table_structure flag).

Unlike the flattened-blob markdown table-structure detection normally
produces (used for 2024's original OCR, see extract_colocados_ocr.py's
docstring), table-structure detection gives real markdown table rows: one
row per candidate, cells already split into Nome / Especialidade /
Instituição / N.º de Ordem / N.º de Cédula. No anchor/position guessing
needed -- just parse the markdown tables directly. Cédula is parsed but
discarded (not used anywhere downstream).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

HEADER_MARKERS = ("nome", "especialidade", "instituição", "instituicao")


@dataclass
class OcrTablePlacement:
    year: int
    ordering_number: int
    specialty: str
    institution: str


def _table_rows(markdown_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first_lower = cells[0].lower()
        if any(marker in " ".join(cells).lower() for marker in HEADER_MARKERS) and (
            "nome" in first_lower or first_lower == "nome"
        ):
            continue
        rows.append(cells)
    return rows


# RapidOCR drops accents inconsistently ("Cirurgia Cardiaca" for "Cirurgia
# Cardíaca") and sometimes prints "/" where the source has "e" ("Ginecologia
# / Obstetricia" for "Ginecologia e Obstetrícia"). Folding accents away and
# treating "/" as a word-separator before comparing catches these without
# needing a hardcoded variant per misread.
def _normalize_specialty_ocr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[/,.]", " ", folded.upper())
    words = [w for w in folded.split() if w not in {"E", "DE", "DA", "DO", "DAS", "DOS"}]
    return " ".join(words)


def parse_ocr_table(markdown_path: str, year: int, known_specialties: set[str]) -> list[OcrTablePlacement]:
    text = open(markdown_path, encoding="utf-8").read()

    from specialty_mapping import CANONICAL_MAP

    specialty_lookup: dict[str, str] = {_normalize_specialty_ocr(s): s for s in known_specialties}
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            specialty_lookup.setdefault(_normalize_specialty_ocr(variant), canonical)

    results: list[OcrTablePlacement] = []
    for cells in _table_rows(text):
        if len(cells) < 5:
            continue
        _name, specialty_raw, institution, ordem_raw, cedula_raw = cells[:5]
        specialty = specialty_lookup.get(_normalize_specialty_ocr(specialty_raw))
        if specialty is None:
            continue
        ordem_digits = re.sub(r"\D", "", ordem_raw)
        cedula_digits = re.sub(r"\D", "", cedula_raw)
        if not ordem_digits or len(cedula_digits) != 5:
            continue
        ordering_number = int(ordem_digits)
        institution = re.sub(r"\s+", " ", institution).strip(" -/,")
        if ordering_number > 0 and institution:
            results.append(OcrTablePlacement(year, ordering_number, specialty, institution))

    return results


if __name__ == "__main__":
    import csv
    import sys
    from collections import Counter

    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/ocr_cache/2024-colocados-tablestruct.md"
    year = int(re.search(r"20\d\d", path).group(0))

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f) if row["year"] != str(year)}

    rows = parse_ocr_table(path, year, known)
    print(f"{len(rows)} rows")
    orders = Counter(r.ordering_number for r in rows)
    dupes = {k: v for k, v in orders.items() if v > 1}
    print(f"{len(dupes)} duplicate ordering numbers (out of {len(rows)} rows)")
    specs = Counter(r.specialty for r in rows)
    print(f"{len(specs)} distinct specialties")
    for r in rows[:10]:
        print(r)
