"""Full-row (specialty + institution + ordering number) extraction for
2024-colocados.md, the OCR markdown for that year's scanned placement PDF.

2024's OCR flattens each page's table into one giant blob per page, but the
markdown converter still marks the original per-cell boundaries with a
double space -- splitting on that recovers the exact original per-cell
token stream. Once split, each record's fields turn out to always appear in
this fixed, decipherable order:

    [institution head fragment(s)] [Name] [Specialty]
    [institution tail fragment(s)] [Ordem] [Cedula]

i.e. the source table's institution column wraps across 1-3 lines, and the
OCR reading order puts the candidate's Name and Especialidade in the middle
of that wrap instead of after it. Ordem is a bare 1-4 digit token and
Cedula immediately follows as a bare 5-digit token -- unambiguous anchors,
same as every other extractor in this pipeline. Specialty is matched
against the known specialty list (extended with spelling variants from
specialty_mapping.CANONICAL_MAP, same as extract_colocados_ocr.py); the
token immediately before a specialty match is the candidate's Name.
Institution is every other token between one record's Cedula and the next
record's Name, joined back together in original order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CELL_SPLIT = re.compile(r"  +")
NUMBER_TOKEN = re.compile(r"^\d+$")
HEADER_TOKENS = {
    "nome", "especialidade", "instituicao", "instituição", "ordem", "cedula", "cédula",
}


@dataclass
class Ocr2024Placement:
    year: int
    ordering_number: int
    specialty: str
    institution: str


def _is_header_token(token: str) -> bool:
    t = token.strip().lower()
    # "N° de", "N ode", "Nde", "N oe" etc -- all OCR noise for the two
    # "N.º de Ordem" / "N.º de Cédula" header labels.
    if re.fullmatch(r"n[°ºo]?\s*(de)?\s*(ordem|cedula|c[ée]dula|oe|ode)?\.?", t):
        return True
    return t in HEADER_TOKENS


def _page_blobs(markdown_text: str) -> list[str]:
    blobs = []
    for line in markdown_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cell = line.strip("|").strip()
        if "Especialidade" not in cell and "especialidade" not in cell.lower():
            continue
        blobs.append(cell)
    return blobs


def parse_ocr_2024(markdown_path: str, year: int, known_specialties: set[str]) -> list[Ocr2024Placement]:
    text = open(markdown_path, encoding="utf-8").read()

    from specialty_mapping import CANONICAL_MAP

    specialty_lookup: dict[str, str] = {s.upper(): s for s in known_specialties}
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            specialty_lookup.setdefault(variant.upper(), canonical)

    results: list[Ocr2024Placement] = []

    for blob in _page_blobs(text):
        tokens = [t.strip() for t in CELL_SPLIT.split(blob) if t.strip()]
        # Drop the header tokens repeated at the start of every page's blob.
        while tokens and _is_header_token(tokens[0]):
            tokens.pop(0)

        i = 0
        record_start = 0  # index of first "institution head" token for the record in progress
        while i < len(tokens):
            token_upper = tokens[i].upper()
            if token_upper in specialty_lookup and i > record_start:
                specialty = specialty_lookup[token_upper]
                name_idx = i - 1
                # institution head = everything from this record's start up to (not incl.) the name
                head = tokens[record_start:name_idx]
                # scan forward for the Ordem/Cedula anchor: two consecutive
                # numeric tokens, second one exactly 5 digits.
                j = i + 1
                anchor = None
                while j + 1 < len(tokens):
                    if (
                        NUMBER_TOKEN.match(tokens[j])
                        and NUMBER_TOKEN.match(tokens[j + 1])
                        and len(tokens[j + 1]) == 5
                    ):
                        anchor = j
                        break
                    j += 1
                if anchor is None:
                    i += 1
                    continue
                tail = tokens[i + 1 : anchor]
                ordering_number = int(tokens[anchor])
                institution = re.sub(r"\s+", " ", " ".join(head + tail)).strip(" -/,")
                if institution and ordering_number > 0:
                    results.append(Ocr2024Placement(year, ordering_number, specialty, institution))
                record_start = anchor + 2
                i = record_start
                continue
            i += 1

    return results


if __name__ == "__main__":
    import sys
    from collections import Counter

    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/ocr_cache/2024-colocados.md"
    year = 2024

    import csv

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f) if row["year"] != "2024"}

    rows = parse_ocr_2024(path, year, known)
    print(f"{len(rows)} rows")
    orders = Counter(r.ordering_number for r in rows)
    dupes = {k: v for k, v in orders.items() if v > 1}
    print(f"{len(dupes)} duplicate ordering numbers (out of {len(rows)} rows)")
    for r in rows[:15]:
        print(r)
