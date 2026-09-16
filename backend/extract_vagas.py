"""Parse a vagas-YYYY.pdf (seat offers) into structured rows.

These PDFs are native-text (no OCR needed -- confirmed the embedded text
decodes to correct Unicode, e.g. 'atologica' -> 'Patológica'). The wrinkle
is that the seat-count column is vertically centered against multi-line
left-hand entries, so "same text line == same table row" (what a naive
`pdftotext -layout` read assumes) is wrong -- numbers can land next to the
wrong row. We match each number to its nearest left-hand row by y-position
instead (the same fallback docling's TableFormer does internally, just
without the heavy model -- these are cleanly left-indented text and a
right-aligned number column, no table-structure model needed).

Layout, left column, 3 indent levels (points from page left, calibrated
per-document since margins can drift slightly between years):
    Specialty   (indent level 0)
       Region / ARS   (indent level 1)
          Institution   (indent level 2)
Numbers column is right-aligned, x0 far to the right of all three levels.

Known limitation: "Medicina Geral e Familiar" (family medicine) nests one
level deeper than every other specialty (specialty -> ARS region -> ACES
sub-region -> individual clinic/USF, hundreds of them), so its
institution-level rows land one indent level short and get misread as
extra bogus "specialties". Its specialty-level and region-level totals are
unaffected. Fixing this needs a 4th indent level special-cased for that one
specialty -- not done yet, flagged here instead of silently shipping wrong
per-clinic numbers for family medicine.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import fitz

FOOTNOTE_MARKER = re.compile(r"\s*[a-z]\)\s*$")
BOILERPLATE = re.compile(
    r"P.gina|Tel\.|Fax:|Email:|Administra..o Central do Sistema|"
    r"Parque de Sa.de|www\.|^Especialidade/|^Aut.noma/Institui..o"
)
HEADER_MARKERS = ("Especialidade/Administra",)


@dataclass
class VagaRow:
    year: int
    specialty: str
    region: str | None
    institution: str | None
    seats: int


def _page_lines(page: fitz.Page) -> list[dict]:
    """Group words into (block,line) groups; return sorted top-to-bottom."""
    words = page.get_text("words")
    lines: dict[tuple[int, int], list[tuple]] = {}
    for x0, y0, x1, y1, text, block_no, line_no, word_no in words:
        lines.setdefault((block_no, line_no), []).append((x0, y0, y1, text))
    out = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        x0 = ws[0][0]
        y0 = min(w[1] for w in ws)
        y1 = max(w[2] for w in ws)
        text = " ".join(w[3] for w in ws)
        out.append({"x0": x0, "y0": y0, "y1": y1, "text": text})
    out.sort(key=lambda ln: ln["y0"])
    return out


def _calibrate_indent_levels(doc: fitz.Document, sample_pages: int = 6) -> list[float]:
    """Find the 3 left-column x0 clusters (specialty/region/institution)."""
    counts: Counter[int] = Counter()
    header_seen = False
    for page in doc[: min(sample_pages, doc.page_count)]:
        for line in _page_lines(page):
            text = line["text"].strip()
            if not header_seen:
                if any(m in text for m in HEADER_MARKERS):
                    header_seen = True
                continue
            if not text or re.fullmatch(r"\d+", text) or BOILERPLATE.search(text):
                continue
            if line["x0"] > 300:  # skip anything not in the left text column
                continue
            counts[round(line["x0"])] += 1
    # Take the 3 most frequent x0s with a non-trivial count, sorted left-to-right.
    common = [x0 for x0, n in counts.most_common(8) if n >= 3]
    levels = sorted(common)[:3]
    if len(levels) < 3:
        raise ValueError(f"could not calibrate 3 indent levels, found: {counts}")
    return levels


def _classify_level(x0: float, levels: list[float]) -> int:
    return min(range(3), key=lambda i: abs(x0 - levels[i]))


def parse_vagas_pdf(path: str, year: int) -> list[VagaRow]:
    doc = fitz.open(path)
    levels = _calibrate_indent_levels(doc)

    text_rows: list[dict] = []  # {level, text, y0, y1, page}
    number_tokens: list[dict] = []  # {value, y0, page}
    header_seen = False

    for page_no, page in enumerate(doc):
        for line in _page_lines(page):
            raw = line["text"].strip()
            if not raw:
                continue
            if not header_seen:
                if any(m in raw for m in HEADER_MARKERS):
                    header_seen = True
                continue
            if BOILERPLATE.search(raw):
                continue

            if re.fullmatch(r"\d+", raw):
                number_tokens.append(
                    {"value": int(raw), "y0": line["y0"], "page": page_no}
                )
                continue

            # A left-column text row may have its own inline trailing number.
            tokens = raw.split()
            inline_number = None
            if tokens and re.fullmatch(r"\d+", tokens[-1]) and line["x0"] < 300:
                inline_number = int(tokens[-1])
                tokens = tokens[:-1]
            text = FOOTNOTE_MARKER.sub("", " ".join(tokens)).strip()
            if not text:
                continue

            level = _classify_level(line["x0"], levels)
            text_rows.append(
                {
                    "level": level,
                    "text": text,
                    "y0": line["y0"],
                    "y1": line["y1"],
                    "page": page_no,
                }
            )
            if inline_number is not None:
                number_tokens.append(
                    {"value": inline_number, "y0": line["y0"], "page": page_no}
                )

    # Match each number to the nearest text row on the same page (by y-distance).
    rows_by_page: dict[int, list[dict]] = {}
    for r in text_rows:
        rows_by_page.setdefault(r["page"], []).append(r)

    matches: list[tuple[dict, dict]] = []
    for num in number_tokens:
        candidates = rows_by_page.get(num["page"], [])
        if not candidates:
            continue
        nearest = min(candidates, key=lambda r: abs(r["y0"] - num["y0"]))
        matches.append((nearest, num))

    # Walk matches in document order, tracking open specialty/region context,
    # and emit one output row per institution-level match.
    results: list[VagaRow] = []
    current_specialty: str | None = None
    current_region: str | None = None
    # also need specialty/region context even for rows with no own number
    ordered_text_rows = sorted(text_rows, key=lambda r: (r["page"], r["y0"]))
    row_context: dict[int, tuple[str | None, str | None]] = {}
    for r in ordered_text_rows:
        if r["level"] == 0:
            current_specialty = r["text"]
            current_region = None
        elif r["level"] == 1:
            current_region = r["text"]
        row_context[id(r)] = (current_specialty, current_region)

    for row, num in matches:
        if row["text"] in ("Total Geral", "Total geral"):
            continue
        specialty, region = row_context[id(row)]
        if row["level"] == 2:  # institution
            results.append(
                VagaRow(year, specialty, region, row["text"], num["value"])
            )
        elif row["level"] == 1:  # region-only line, no institution breakdown
            results.append(VagaRow(year, specialty, row["text"], None, num["value"]))
        elif row["level"] == 0:  # specialty total
            results.append(VagaRow(year, row["text"], None, None, num["value"]))

    return results


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/vagas/vagas-2023.pdf"
    year = int(re.search(r"20\d\d", path).group(0))
    rows = parse_vagas_pdf(path, year)
    print(f"{len(rows)} rows")

    # Sanity check: institution-level seats should sum to the specialty total.
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
