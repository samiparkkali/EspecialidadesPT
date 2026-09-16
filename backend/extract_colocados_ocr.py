"""Extracts (specialty, ordering_number) pairs from OCR'd colocados markdown
(see backend/ocr_convert.py) for scanned placement-result PDFs.

The source table's rows don't survive OCR as clean grid cells -- markdown
export flattens everything into one blob of text, with words sometimes out
of their original column order (an OCR/layout artifact, not fixable
without redoing extraction with layout awareness). But two things survive
reliably:

  1. Every specialty name still appears as an intact contiguous phrase, in
     document order, once per placed candidate.
  2. Immediately near every specialty mention there's a distinctive number
     pair: N. de Ordem (the ordering number, 1-4 digits) followed shortly
     by N. de Cedula (medical license number, always 5 digits). No other
     number pattern in the document looks like this.

So: scan the flattened text left to right, track whichever known specialty
name was most recently seen (same technique as
extract_vagas_totals.py's sequential state machine, for the same reason --
region/institution words in between never match a specialty name), and
attribute each ordem/cedula pair encountered to that specialty.

Institution isn't extracted this way -- OCR word order scrambles which
institution phrase belongs to which candidate too much to trust
positionally. This only recovers specialty + ordering number, which is
what the ordering-number "what could I get into" prediction actually
needs; full per-institution cutoffs for these years remain a gap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUMBER_PAIR = re.compile(r"\b(\d{1,4})\s+(\d{5})\b")


@dataclass
class OcrPlacement:
    year: int
    ordering_number: int
    specialty: str


def parse_ocr_colocados(markdown_path: str, year: int, known_specialties: set[str]) -> list[OcrPlacement]:
    text = open(markdown_path, encoding="utf-8").read()

    from specialty_mapping import CANONICAL_MAP

    # Search for every known spelling variant too (a year's OCR text can
    # use a different wording than colocados.csv's reference set, e.g.
    # "Doenças Infeciosas" vs "Doenças Infecciosas"), mapping each match
    # back to its canonical name. Longest patterns first so e.g. "Medicina
    # Geral E Familiar" doesn't get shadowed by a shorter substring match.
    search_patterns: dict[str, str] = {s: s for s in known_specialties}
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            search_patterns.setdefault(variant, canonical)

    mentions: list[tuple[int, str]] = []
    for pattern, canonical in sorted(search_patterns.items(), key=lambda kv: len(kv[0]), reverse=True):
        for m in re.finditer(re.escape(pattern), text, re.IGNORECASE):
            mentions.append((m.start(), canonical))
    mentions.sort()

    results: list[OcrPlacement] = []
    mention_idx = 0
    current_specialty: str | None = None

    for m in NUMBER_PAIR.finditer(text):
        pos = m.start()
        while mention_idx < len(mentions) and mentions[mention_idx][0] < pos:
            current_specialty = mentions[mention_idx][1]
            mention_idx += 1
        if current_specialty is None:
            continue
        ordering_number = int(m.group(1))
        if ordering_number == 0:
            continue
        results.append(OcrPlacement(year, ordering_number, current_specialty))

    return results


if __name__ == "__main__":
    import csv
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/ocr_cache/2024-colocados.md"
    year = int(re.search(r"20\d\d", path).group(0))

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f)}

    results = parse_ocr_colocados(path, year, known)
    print(f"{len(results)} placements")
    orderings = [r.ordering_number for r in results]
    if orderings:
        print(f"ordering_number range: {min(orderings)}..{max(orderings)}")
    for r in results[:10]:
        print(r)
