"""Full institution/region-level parsing for years (2021, 2022, 2024) whose
PDFs use explicit "Subtotal"/"Total da Especialidade" labels instead of
extract_vagas.py's position-based indent calibration, which flips between years.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))

SUBTOTAL_LABEL = re.compile(r"^Subtotal\b", re.IGNORECASE)
# Anchored (not a substring search) so an institution like "Centro Hospitalar
# de Leiria" doesn't get misread as the region header via its "Centro" prefix.
REGION_HEADER = re.compile(
    r"^(Administra[çc][ãa]o Regional de Sa[úu]de|Regi[ãa]o Aut[óo]noma)",
    re.IGNORECASE,
)
# 2024/2025 print bare short region names; exact match only, since no
# institution name is ever just "Centro" alone.
SHORT_REGION_NAMES = {
    "norte", "centro", "lisboa e vale do tejo", "alentejo", "algarve",
    "açores", "acores", "raa", "madeira", "ram",
}


def _is_region_header(text: str) -> bool:
    return bool(REGION_HEADER.match(text)) or text.strip().lower() in SHORT_REGION_NAMES
TOTAL_LABEL = re.compile(r"total\s+da\s+especialidade", re.IGNORECASE)
# A bare seat count, optionally prefixed by a footnote letter (2022's "a) 8").
FOOTNOTE_NUM = re.compile(r"^(?:[a-z]\)\s*)?(\d+)$", re.IGNORECASE)
# Document-level grand-total rows (after all specialties) would otherwise
# fall into the "must be an institution" catch-all with bogus huge seat counts.
GRAND_TOTAL_LABEL = re.compile(r"^Total\s+(Nacional|Geral|em\b)", re.IGNORECASE)

# Repeated page header/footer text that would otherwise land mid-table and
# get misread as a bogus institution row.
PAGE_BOILERPLATE = re.compile(
    r"^\d+/\d+$"                                    # page number, e.g. "46/46"
    r"|^\d{1,2}-\d{1,2}-\d{4}$"                      # date, e.g. "31-10-2024"
    r"|Aviso n\.?\s*[ºo]"                            # "Aviso n.º ..."
    r"|^N\.?\s*[ºo]\s*\d"                            # "N.º 212"
    r"|SUPLEMENTO"
    r"|^SA[ÚU]DE$"
    r"|^Especialidade/"                              # column header repeat
    r"|^N[úu]mero\s+de\s+[Vv]agas"                   # column header repeat
    r"|Regional de Sa[úu]de ou Regi[ãa]o Aut[óo]noma" # column header repeat, not a real region
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
        prev_key: tuple[int, int] | None = None
        for key in sorted(by_line):
            ws = sorted(by_line[key])
            text = " ".join(t for _, t in ws).strip()
            if not text:
                continue
            block_no, line_no = key
            # A long institution name can wrap onto the very next line_no in
            # the same block with no seat count of its own (e.g. "...Centro
            # de Saúde Estreito de Câmara de" / "Lobos") -- merge it back into
            # the row it continues rather than emitting it as a bogus new row.
            if (
                out
                and prev_key is not None
                and prev_key[0] == block_no
                and line_no == prev_key[1] + 1
                and not re.search(r"\d", text)
                and not re.search(r"\d", out[-1])
            ):
                out[-1] = f"{out[-1]} {text}"
            else:
                out.append(text)
            prev_key = key
    return out


def _clean(text: str) -> str:
    """Strip dot-leaders ("Nome . . . . .") and trailing footnote markers.
    The leader dots are usually space-separated in the extracted text, not
    consecutive, so the pattern has to allow whitespace between them --
    otherwise institutions ending in a dot-leader (most of them) keep the
    leader as part of the "canonical" name and never match their own
    dot-free spelling from another year."""
    text = re.sub(r"(?:\.\s*){2,}.*$", "", text).strip()
    # A real footnote marker is its own token ("... 8 a)"), not the tail of a
    # word -- "Madeira)" ends in "a)" too and must NOT be treated as one.
    text = re.sub(r"(?<![a-zA-Z])\s*[a-z]\)\s*$", "", text).strip()
    return text


# Header wording drifts year to year in ways that are invisible to a reader
# but break an exact string match: a comma present one year and absent the
# next ("Cirurgia Plástica, Reconstrutiva e Estética" vs "... Reconstrutiva
# e Estética"), or a connector word silently dropped ("Medicina Física e de
# Reabilitação" vs "Medicina Física Reabilitação"). An unrecognized header
# doesn't just lose that specialty -- it also gets swallowed as bogus extra
# rows under whichever specialty came right before it. Normalizing away
# punctuation and connector words before comparing catches these.
_SPECIALTY_STOPWORDS = {"E", "DE", "DA", "DO", "DAS", "DOS"}


def _normalize_specialty(text: str) -> str:
    stripped = re.sub(r"[,.]", " ", text.upper())
    words = [w for w in stripped.split() if w not in _SPECIALTY_STOPWORDS]
    return " ".join(words)


def parse_vagas_labeled(path: str, year: int, known_specialties: set[str]) -> list[LabeledVagaRow]:
    doc = fitz.open(path)
    lines = [_clean(t) for t in _lines(doc)]
    lines = [t for t in lines if t and not PAGE_BOILERPLATE.search(t)]
    from specialty_mapping import CANONICAL_MAP

    known_norm = {_normalize_specialty(s): s for s in known_specialties}
    variant_pairs: list[tuple[str, str]] = [(s, s) for s in known_specialties]
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            known_norm.setdefault(_normalize_specialty(variant), canonical)
            variant_pairs.append((variant, canonical))
    # Longest spelling first, so e.g. "Cirurgia Plástica..." wins over a
    # shorter specialty name that happens to be its own prefix.
    variant_pairs.sort(key=lambda vp: len(vp[0]), reverse=True)

    rows: list[LabeledVagaRow] = []
    current_specialty: str | None = None
    current_region: str | None = None

    i = 0
    n = len(lines)
    while i < n:
        text = lines[i]

        if GRAND_TOTAL_LABEL.match(text):
            break  # end of per-specialty table, summary section follows

        # A wrapped specialty name's first line can itself be a different,
        # valid, shorter specialty -- check the two-line join first.
        if i + 1 < n:
            combined = _normalize_specialty(f"{text} {lines[i + 1]}")
            if combined in known_norm:
                current_specialty = known_norm[combined]
                current_region = None
                i += 2
                continue

        norm_text = _normalize_specialty(text)
        if norm_text in known_norm:
            current_specialty = known_norm[norm_text]
            current_region = None
            i += 1
            continue

        # A specialty header is sometimes glued to the very next line with no
        # line break at all in the source PDF (2021's first specialty on a
        # page, e.g. "ANESTESIOLOGIA Administração Regional de Saúde de
        # Lisboa e Vale do Tejo, I.P." as one extracted line) -- an
        # unrecognized header doesn't just lose that one line, it silently
        # drops the entire specialty's data under whichever specialty came
        # before it. If `text` starts with a known specialty spelling
        # followed by more text, split it: recognize the specialty and put
        # the remainder back to be parsed as its own line next.
        # Some pages also glue a leftover column-header fragment onto the
        # FRONT of the specialty name instead ("de Vagas ANATOMIA
        # PATOLÓGICA ..." -- the tail of "Número de Vagas" from the repeated
        # header row) -- search rather than anchor at the very start, but
        # only accept a short leading fragment so this can't misfire on an
        # institution name that happens to contain a specialty word deep
        # inside a much longer line.
        glued = None
        for variant, canonical in variant_pairs:
            m = re.search(re.escape(variant) + r"(?=\s|$)", text, re.IGNORECASE)
            if m and m.start() <= 20:
                glued = (canonical, text[m.end() :].strip())
                break
        if glued:
            current_specialty, remainder = glued
            current_region = None
            if remainder:
                lines[i] = remainder
            else:
                i += 1
            continue

        if _is_region_header(text):
            current_region = text
            i += 1
            continue

        # Most years print "Total da Especialidade <N>"; some (2024) print
        # just the bare number directly under the specialty name, before any
        # region section -- that's still the specialty total, not a stray line.
        bare_total = FOOTNOTE_NUM.fullmatch(text)
        if bare_total and current_specialty and current_region is None:
            rows.append(LabeledVagaRow(year, current_specialty, None, None, int(bare_total.group(1))))
            i += 1
            continue

        # Subtotal/total lines carry their number inline; institution names
        # have it on the following line instead.
        is_total = TOTAL_LABEL.search(text)
        is_subtotal = SUBTOTAL_LABEL.match(text)

        m = re.search(r"(\d+)\s*$", text)
        if m and (is_total or is_subtotal):
            seats = int(m.group(1))
            consumed = 1
        elif i + 1 < n and (fm := FOOTNOTE_NUM.fullmatch(lines[i + 1])):
            # 2022 marks some seat counts with a footnote letter, e.g. "a) 8"
            # (protocol/shared seats) -- the number itself is the real count.
            seats = int(fm.group(1))
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
