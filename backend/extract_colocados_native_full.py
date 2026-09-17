"""Full-row (specialty + institution + ordering number) extraction for
colocados PDFs whose native text has no ruled table lines --
page.find_tables() (extract_colocados.py's approach) finds nothing, but the
text itself is clean, native, alphabetically-listed records of
Nome / Especialidade / Instituição / Cédula / Nº de Ordem, five lines each.

Same anchor strategy as extract_colocados_ocr_full.py (known specialty name
-> next number pair -> institution is the text between them), but the
number pair here is (5-digit cédula, 1-4 digit ordem) in that order, the
reverse of the 2025 OCR text's order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import fitz

NUMBER_PAIR = re.compile(r"\b(\d{5})\s+(\d{1,4})\b")

# 2022's PDF has a font/cmap glitch (confirmed absent from every other year)
# that occasionally renders a digit as a similar-shaped letter -- "5"->"S",
# "8"->"B", "0"->"O", "1"->"l" (also visible elsewhere in this same document
# as "Gala" for "Gaia" and "EFE." for "E.P.E."). Left unhandled, ~3% of
# ordering-number pairs in 2022 fail the plain NUMBER_PAIR match and their
# whole placement row is silently dropped. This fallback pattern is only
# tried where the strict digit-only match already failed, and only accepts
# a token if it has at least one real digit, to avoid matching unrelated
# 5-9 character runs of plain text.
_LOOKALIKE_DIGITS = str.maketrans({"S": "5", "B": "8", "O": "0", "l": "1"})
# One 2022 record prints its ordering number with a thousands-separator dot
# ("2.754") -- rare (a single occurrence in the whole document) but without
# this the plain 1-4-digit capture stops at "2" and collides with any other
# record whose real ordem is 2.
_NUMBER_PAIR_LOOKALIKE = re.compile(r"\b([\dSBOl]{5})\s+([\dSBOl]{1,2}\.\d{3}|[\dSBOl]{1,4})\b")


def _has_real_digit(token: str) -> bool:
    return any(ch.isdigit() for ch in token)

# "Psiquiatria da Infância e da Adolescência" is long enough that the PDF's
# column layout wraps it across two lines, and because a record's Nome line
# sits right after the specialty line, the wrap boundary lands INSIDE the
# specialty name with a candidate's name interposed between the two halves
# (e.g. "Psiquiatria da Infância e da\nFilipa ... Catarro\nAdolescência").
# The exact-substring match can never see this as one string, so every
# placement for this specialty was silently dropped in 2021/2022 (native-text
# years). The source also has real typos in some of these wraps ("Psiqxiatria",
# "e do" for "e da", "Adolescéncia" without the ê) -- tolerate those rather
# than fix each one individually, since they're a single scanned/typed source
# document, not something we can correct upstream.
_PSIQ_INFANCIA_RE = re.compile(
    r"Psiqx?uiatria\s+da\s+Inf[âa]ncia\s+e\s+d[ao]\s*"
    r"(?:.{0,80}?\s)??"
    r"Adolesc[êe]ncia",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class NativeFullPlacement:
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


def parse_colocados_native_full(
    path: str, year: int, known_specialties: set[str]
) -> list[NativeFullPlacement]:
    doc = fitz.open(path)
    text = "\n".join(page.get_text() for page in doc)
    patterns = _search_patterns(known_specialties)

    # Some known specialty names are literal substrings of others
    # ("Urologia" inside "Neurologia", "Radiologia" inside
    # "Neurorradiologia", "Cardiologia" inside "Cardiologia Pediátrica",
    # "Psiquiatria" inside all its child specialties). Collecting every
    # pattern's matches independently and then just walking to the LAST
    # mention before each number pair means a real "Neurologia" heading
    # gets silently overwritten by the nested "Urologia" match that starts
    # a few characters later -- so overlapping matches must be resolved to
    # the longest one, not the textually-last one.
    from specialty_mapping import canonicalize_specialty

    psiq_infancia_canonical = canonicalize_specialty("Psiquiatria da Infância e da Adolescência")

    raw_mentions: list[tuple[int, int, str]] = []
    for pattern, canonical in sorted(patterns.items(), key=lambda kv: len(kv[0]), reverse=True):
        for m in re.finditer(re.escape(pattern), text, re.IGNORECASE):
            raw_mentions.append((m.start(), m.end(), canonical))
    if psiq_infancia_canonical in known_specialties:
        for m in _PSIQ_INFANCIA_RE.finditer(text):
            raw_mentions.append((m.start(), m.end(), psiq_infancia_canonical))
    raw_mentions.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    mentions: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, canonical in raw_mentions:
        if start < last_end:
            continue
        mentions.append((start, end, canonical))
        last_end = end

    results: list[NativeFullPlacement] = []
    mi = 0
    for pair in _NUMBER_PAIR_LOOKALIKE.finditer(text):
        cedula_token, ordem_token = pair.group(1), pair.group(2)
        if not (_has_real_digit(cedula_token) and _has_real_digit(ordem_token)):
            continue
        pair_pos = pair.start()
        chosen = None
        while mi < len(mentions) and mentions[mi][0] < pair_pos:
            chosen = mentions[mi]
            mi += 1
        if chosen is None:
            continue
        _, spec_end, specialty = chosen
        institution = re.sub(r"\s+", " ", text[spec_end:pair_pos]).strip(" -/|")
        if not institution:
            continue
        ordering_number = int(ordem_token.translate(_LOOKALIKE_DIGITS).replace(".", ""))
        if ordering_number == 0:
            continue
        results.append(NativeFullPlacement(year, ordering_number, specialty, institution))

    return results


if __name__ == "__main__":
    import csv
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/colocacoes/2021-colocados.pdf"
    year = int(re.search(r"20\d\d", path).group(0))

    with open("data/processed/colocados.csv", encoding="utf-8") as f:
        known = {row["specialty"] for row in csv.DictReader(f)}

    results = parse_colocados_native_full(path, year, known)
    print(f"{len(results)} placements")
    for r in results[:15]:
        print(r)
