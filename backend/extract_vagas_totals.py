"""Specialty-level (not institution-level) seat totals for years whose
vagas-YYYY.pdf uses an explicit "Total da Especialidade N" label, instead
of extract_vagas.py's position-based row matching (which only handles
2023's particular layout -- see its docstring).

2021, 2022 and 2024 all print "Total da Especialidade"/"Total da
especialidade" (casing varies) right next to the specialty name -- the
name is on the line immediately before or immediately after the label,
depending on the year (2021/2022 put the name after; 2024 puts it before).
Whichever neighbor matches a known specialty name is used, so this doesn't
need to know a year's specific ordering up front.

This intentionally does NOT extract per-region/per-institution rows for
these years -- only the specialty's yearly grand total. That's enough for
year-over-year specialty comparisons (the Evolution chart); full hospital-
level breakdown for these years is a known gap, same as institution-level
rows already are for "Medicina Geral e Familiar" in 2023 (see
extract_vagas.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import fitz

TOTAL_LABEL = re.compile(r"total\s+da\s+especialidade", re.IGNORECASE)


@dataclass
class SpecialtyTotal:
    year: int
    specialty: str
    seats: int


def _lines(doc: fitz.Document) -> list[str]:
    out: list[str] = []
    for page in doc:
        for raw_line in page.get_text().split("\n"):
            line = raw_line.strip()
            if line:
                out.append(line)
    return out


def _clean_name(line: str) -> str:
    # Strip dot-leaders ("Nome . . . . . .") and trailing footnote markers.
    line = re.sub(r"\.{2,}.*$", "", line).strip()
    line = re.sub(r"\s*[a-z]\)\s*$", "", line).strip()
    return line


def parse_specialty_totals(path: str, year: int, known_specialties: set[str]) -> list[SpecialtyTotal]:
    """Sequential top-to-bottom scan tracking whichever specialty name was
    most recently seen, then attributing each "Total da Especialidade" line
    to it. This handles both observed orderings without needing to know
    which one a given year uses: 2021/2022 print the name once at the top
    of a (possibly long) block, with the total only appearing after all of
    that specialty's regions/institutions -- not adjacent to the name at
    all, so a local-window lookback (tried first, see git history) missed
    it. 2024 prints the name immediately before its own total. Either way,
    no specialty name-like line appears *between* a specialty's own header
    and its total (only region/institution names, which don't match
    known_specialties), so "most recently seen" stays correct throughout.
    """
    doc = fitz.open(path)
    lines = _lines(doc)
    results: list[SpecialtyTotal] = []
    known_upper = {s.upper(): s for s in known_specialties}

    current_specialty: str | None = None
    for i, line in enumerate(lines):
        name = _clean_name(line)
        if name.upper() in known_upper:
            current_specialty = known_upper[name.upper()]
            continue

        if not TOTAL_LABEL.search(line) or current_specialty is None:
            continue

        seats = None
        m = re.search(r"(\d+)\s*$", line)
        if m:
            seats = int(m.group(1))
        else:
            for j in range(i + 1, min(i + 3, len(lines))):
                if re.fullmatch(r"\d+", lines[j]):
                    seats = int(lines[j])
                    break
        if seats is None:
            continue

        results.append(SpecialtyTotal(year, current_specialty, seats))
        current_specialty = None  # each total consumed once

    return results


if __name__ == "__main__":
    import csv
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/vagas/vagas-2021.pdf"
    year = int(re.search(r"20\d\d", path).group(0))

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f)}

    results = parse_specialty_totals(path, year, known)
    print(f"{len(results)} specialty totals")
    for r in results[:20]:
        print(r)
