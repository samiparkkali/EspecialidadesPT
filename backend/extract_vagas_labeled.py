"""Full institution/region-level parsing for years whose vagas-YYYY.pdf uses
explicit "Subtotal"/"Total da Especialidade" labels (2021, 2022, 2024 --
see extract_vagas.py's docstring for why 2023 needs a different, position-
based approach instead, and extract_vagas_totals.py for the specialty-total
-only version of this that predates this file).

Unlike position-based indent calibration (fragile -- x0 for institution vs.
region flips between 2021 and 2022, see git history), this only needs two
structural facts that hold across all three years:

  1. A region header line ("Administração Regional de Saúde X, I.P." /
     "Região Autónoma X") has no number of its own -- it's a pure section
     divider, the next line is either an institution or "Subtotal".
  2. Every institution name, "Subtotal", and "Total da Especialidade" line
     is immediately followed by its own number on the next line.

So: sequential scan, classify each label line by matching known patterns
(specialty via the same whitelist-matching extract_vagas_totals.py uses,
region via region_mapping.region_key, "Subtotal"/"Total da Especialidade"
via fixed text), and treat anything else as an institution name.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))

SUBTOTAL_LABEL = re.compile(r"^Subtotal\b", re.IGNORECASE)
# Anchored to the start of the line -- region_mapping.region_key() does a
# loose substring search (fine for vagas.csv's already-clean region
# column), which false-positives here: an institution name like "Centro
# Hospitalar de Leiria, E.P.E." contains the region pattern word "Centro"
# and would otherwise get misread as the region header itself.
REGION_HEADER = re.compile(
    r"^(Administra[çc][ãa]o Regional de Sa[úu]de|Regi[ãa]o Aut[óo]noma)",
    re.IGNORECASE,
)
# 2024/2025-style files print bare short region names instead of the full
# "Administração Regional de Saúde X" phrasing -- exact match only (not a
# substring search), since e.g. "Centro" alone as a *complete* line is
# safe (no institution name is ever just that one word).
SHORT_REGION_NAMES = {
    "norte", "centro", "lisboa e vale do tejo", "alentejo", "algarve",
    "açores", "acores", "madeira", "ram",
}


def _is_region_header(text: str) -> bool:
    return bool(REGION_HEADER.match(text)) or text.strip().lower() in SHORT_REGION_NAMES
TOTAL_LABEL = re.compile(r"total\s+da\s+especialidade", re.IGNORECASE)
# Document-level grand-total rows (a summary section after all specialties,
# e.g. "Total Nacional", "Total em Áreas Hospitalares") -- not per-
# specialty data, and their huge numbers get misread as institution seat
# counts if not excluded explicitly (they don't match TOTAL_LABEL/
# SUBTOTAL_LABEL/a known specialty/a known region, so without this they
# fall into the "must be an institution" catch-all).
GRAND_TOTAL_LABEL = re.compile(r"^Total\s+(Nacional|Geral|em\b)", re.IGNORECASE)

# Page header/footer text repeated at every page break (page numbers,
# "Aviso n.º ...", the date/dispatch line, "SUPLEMENTO ... série", and the
# column-header row itself) -- left unfiltered, these land mid-table
# between two real rows and get misread as bogus institutions ("N.º 212"
# followed by some unrelated number).
PAGE_BOILERPLATE = re.compile(
    r"^\d+/\d+$"                                    # page number, e.g. "46/46"
    r"|^\d{1,2}-\d{1,2}-\d{4}$"                      # date, e.g. "31-10-2024"
    r"|Aviso n\.?\s*[ºo]"                            # "Aviso n.º ..."
    r"|^N\.?\s*[ºo]\s*\d"                            # "N.º 212"
    r"|SUPLEMENTO"
    r"|^SA[ÚU]DE$"
    r"|^Especialidade/"                              # column header repeat
    r"|^N[úu]mero\s+de\s+[Vv]agas"                   # column header repeat
    r"|Administra[çc][ãa]o Central do Sistema",
    re.IGNORECASE,
)


@dataclass
class LabeledVagaRow:
    year: int
    specialty: str
    region: str | None
    institution: str | None
    seats: int


def _lines(doc: fitz.Document) -> list[str]:
    out: list[str] = []
    for page in doc:
        words = page.get_text("words")
        by_line: dict[tuple[int, int], list[tuple[float, str]]] = {}
        for x0, y0, x1, y1, text, block_no, line_no, word_no in words:
            by_line.setdefault((block_no, line_no), []).append((x0, text))
        for key in sorted(by_line):
            ws = sorted(by_line[key])
            text = " ".join(t for _, t in ws).strip()
            if text:
                out.append(text)
    return out


def _clean(text: str) -> str:
    """Strip dot-leaders ("Nome . . . . .") and trailing footnote markers."""
    text = re.sub(r"\.{2,}.*$", "", text).strip()
    text = re.sub(r"\s*[a-z]\)\s*$", "", text).strip()
    return text


def parse_vagas_labeled(path: str, year: int, known_specialties: set[str]) -> list[LabeledVagaRow]:
    doc = fitz.open(path)
    lines = [_clean(t) for t in _lines(doc)]
    lines = [t for t in lines if t and not PAGE_BOILERPLATE.search(t)]
    from specialty_mapping import CANONICAL_MAP

    known_upper = {s.upper(): s for s in known_specialties}
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            known_upper.setdefault(variant.upper(), canonical)

    rows: list[LabeledVagaRow] = []
    current_specialty: str | None = None
    current_region: str | None = None

    i = 0
    n = len(lines)
    while i < n:
        text = lines[i]

        if GRAND_TOTAL_LABEL.match(text):
            # Ends the per-specialty table; a national/area summary
            # section follows, not more institutions.
            break

        # A long specialty name can wrap across two physical lines (e.g.
        # "Psiquiatria" / "Da Infância E Da Adolescência"), and the first
        # line alone can itself be a *different*, valid, shorter specialty
        # name -- check the two-line concatenation first so the longer
        # compound name wins, or a single-line match would silently
        # misattribute the whole wrapped specialty's data to the shorter
        # one.
        if i + 1 < n:
            combined = f"{text} {lines[i + 1]}".upper()
            if combined in known_upper:
                current_specialty = known_upper[combined]
                current_region = None
                i += 2
                continue

        if text.upper() in known_upper:
            current_specialty = known_upper[text.upper()]
            current_region = None
            i += 1
            continue

        if _is_region_header(text):
            current_region = text
            i += 1
            continue

        # "Subtotal N" / "Total da Especialidade N" carry their number
        # inline; an institution name has it on the following line instead
        # (see this file's docstring / git history for both observed
        # patterns). Try inline first, then the next-line fallback.
        is_total = TOTAL_LABEL.search(text)
        is_subtotal = SUBTOTAL_LABEL.match(text)

        m = re.search(r"(\d+)\s*$", text)
        if m and (is_total or is_subtotal):
            seats = int(m.group(1))
            consumed = 1
        elif i + 1 < n and re.fullmatch(r"\d+", lines[i + 1]):
            seats = int(lines[i + 1])
            consumed = 2
        else:
            i += 1
            continue

        if is_total:
            if current_specialty:
                rows.append(LabeledVagaRow(year, current_specialty, None, None, seats))
        elif is_subtotal:
            if current_specialty and current_region:
                rows.append(LabeledVagaRow(year, current_specialty, current_region, None, seats))
        elif current_specialty and current_region:
            institution = re.sub(r"\d+\s*$", "", text).strip() if consumed == 1 else text
            rows.append(LabeledVagaRow(year, current_specialty, current_region, institution, seats))
        i += consumed

    return rows


if __name__ == "__main__":
    import csv

    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/vagas/vagas-2021.pdf"
    year = int(re.search(r"20\d\d", path).group(0))

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f)}

    rows = parse_vagas_labeled(path, year, known)
    print(f"{len(rows)} rows")
    for r in rows[:15]:
        print(r)

    from collections import defaultdict

    inst_sum: dict[str, int] = defaultdict(int)
    specialty_total: dict[str, int] = {}
    for r in rows:
        if r.institution:
            inst_sum[r.specialty] += r.seats
        elif r.region is None:
            specialty_total[r.specialty] = r.seats
    mismatches = 0
    for spec, total in specialty_total.items():
        got = inst_sum.get(spec, 0)
        if got != total:
            mismatches += 1
            print(f"MISMATCH: {spec!r} total={total} sum(institutions)={got}")
    print(f"{len(specialty_total)} specialties, {mismatches} mismatches")
