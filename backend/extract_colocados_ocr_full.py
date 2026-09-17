"""Full-row (specialty + institution + ordering number) extraction from
OCR'd colocados markdown, for years where the OCR text preserves each
record's reading order (Nome, Especialidade, Instituição, Nº de Ordem,
Nº de Cédula) cleanly -- confirmed true for 2025-colocados.pdf's OCR
output by inspection, NOT true for 2024-colocados.pdf's (its institution
names wrap across two lines in the source table, and OCR reading order
scrambles the wrapped continuation into the *next* record instead of
staying with the current one -- see this file's module-level test output
for both years before trusting this for a given year).

Approach: known specialty names are a reliable anchor (extract_colocados_ocr.py
already established this). Between one ordem/cedula number pair and the
next specialty mention lies: [end of previous institution] [next person's
name]. Between a specialty mention and the following number pair lies the
institution. So: find every (specialty position, next number-pair position)
gap and take the text in between as the institution, trimming the leading
material that's clearly a stray name/institution fragment carried over
from OCR line-wrapping (heuristic: an institution phrase in this dataset
always starts with a capitalized legal/entity word -- ULS, Hospital,
Instituto, Centro, Unidade, Aces, Sesaram, Santa Casa -- so drop any text
before the first such word if one is present).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUMBER_PAIR = re.compile(r"\b(\d{1,4})\s+(\d{5})\b")

_INSTITUTION_START_WORDS = (
    "ULS", "Unidade Local de Saúde", "Hospital", "Instituto",
    "Centro", "Aces", "Sesaram", "Santa Casa", "Clínica",
)
_INSTITUTION_START = re.compile(
    "(" + "|".join(re.escape(w) for w in _INSTITUTION_START_WORDS) + ")",
    re.IGNORECASE,
)


@dataclass
class OcrFullPlacement:
    year: int
    ordering_number: int
    specialty: str
    institution: str


def _search_patterns(known_specialties: set[str]) -> dict[str, str]:
    from specialty_mapping import CANONICAL_MAP

    patterns: dict[str, str] = {s: s for s in known_specialties}
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            patterns.setdefault(variant, canonical)
    return patterns


def _clean_institution(raw: str) -> str:
    raw = re.sub(r"\s+", " ", raw).strip(" -/|")
    m = _INSTITUTION_START.search(raw)
    if m:
        raw = raw[m.start():]
    return raw.strip(" -/|")


def parse_ocr_colocados_full(
    markdown_path: str, year: int, known_specialties: set[str]
) -> list[OcrFullPlacement]:
    text = open(markdown_path, encoding="utf-8").read()
    patterns = _search_patterns(known_specialties)

    # As in extract_colocados_native_full.py: some known specialty names are
    # literal substrings of others ("Urologia" inside "Neurologia",
    # "Radiologia" inside "Neurorradiologia", "Psiquiatria" inside its child
    # specialties). Collecting every pattern's matches independently and
    # walking to the last one before each number pair means a real
    # "Neurologia" mention gets silently overwritten by the nested
    # "Urologia" match a few characters later, so overlaps must resolve to
    # the longest match, not the textually-last one.
    raw_mentions: list[tuple[int, int, str]] = []
    for pattern, canonical in sorted(patterns.items(), key=lambda kv: len(kv[0]), reverse=True):
        for m in re.finditer(re.escape(pattern), text, re.IGNORECASE):
            raw_mentions.append((m.start(), m.end(), canonical))
    raw_mentions.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    mentions: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, canonical in raw_mentions:
        if start < last_end:
            continue
        mentions.append((start, end, canonical))
        last_end = end

    pairs = list(NUMBER_PAIR.finditer(text))

    results: list[OcrFullPlacement] = []
    mi = 0
    for pair in pairs:
        pair_pos = pair.start()
        # advance to the specialty mention immediately before this pair
        chosen = None
        while mi < len(mentions) and mentions[mi][0] < pair_pos:
            chosen = mentions[mi]
            mi += 1
        if chosen is None:
            continue
        _, spec_end, specialty = chosen
        institution_raw = text[spec_end:pair_pos]
        institution = _clean_institution(institution_raw)
        if not institution:
            continue
        ordering_number = int(pair.group(1))
        if ordering_number == 0:
            continue
        results.append(OcrFullPlacement(year, ordering_number, specialty, institution))

    return results


if __name__ == "__main__":
    import csv
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/ocr_cache/2025-colocados.md"
    year = int(re.search(r"20\d\d", path).group(0))

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f)}

    results = parse_ocr_colocados_full(path, year, known)
    print(f"{len(results)} placements with institution")
    for r in results[:15]:
        print(r)
