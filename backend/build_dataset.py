"""Run the full extraction pipeline: PDFs -> data/processed/*.csv -> frontend/public/data/*.json.

Parses every vagas-*.pdf / *-colocados.pdf it can:
  - native-text PDFs are parsed directly (extract_vagas.py / extract_colocados.py)
  - scanned PDFs are skipped here with a warning -- run
    `python backend/ocr_convert.py <in.pdf> data/processed/ocr_cache/<name>.md`
    first (slow, OCR), then extend this script to parse that cached markdown
    once a parser for it exists (see CLAUDE.md's per-year-format note)

Adds a `canonical_institution` column (institution_mapping.py) before
writing CSVs, and mirrors both CSVs as JSON under frontend/public/data/
for the static (GitHub Pages compatible) frontend build.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import fitz

from extract_colocados import parse_colocados_pdf
from extract_colocados_native_full import parse_colocados_native_full
from extract_colocados_ocr import parse_ocr_colocados
from extract_colocados_ocr_full import parse_ocr_colocados_full
from extract_colocados_ocr_table import parse_ocr_table
from extract_vagas import parse_vagas_pdf
from extract_vagas_labeled import parse_vagas_labeled
from institution_mapping import canonicalize
from region_mapping import region_key
from specialty_mapping import canonicalize_specialty

ROOT = Path(__file__).resolve().parent.parent
RAW_VAGAS = ROOT / "data" / "raw" / "vagas"
RAW_COLOC = ROOT / "data" / "raw" / "colocacoes"
PROCESSED = ROOT / "data" / "processed"
FRONTEND_DATA = ROOT / "frontend" / "public" / "data"


def _has_native_text(path: Path) -> bool:
    """Requires most of the sampled pages to have real text, not just one --
    a scanned PDF can still have a native-text cover page (e.g.
    2025-colocados.pdf), which would otherwise pass a "just one page"
    check and get routed to the native parser instead of OCR, silently
    losing everything past the cover.
    """
    doc = fitz.open(path)
    sample = min(5, doc.page_count)
    with_text = sum(1 for i in range(sample) if len(doc[i].get_text().strip()) > 50)
    return with_text >= max(2, sample // 2)


# MGF's 4th nesting level leaks clinic/institution names as fake "specialty"
# rows; these prefixes catch them regardless of specialty-name wording drift.
_INSTITUTION_PREFIXES = (
    "USF ", "UCSP ", "ULS ", "ULS", "ACES ", "Aces ", "Administra",
    "Hospital ", "Centro ", "Instituto ", "Unidade ", "Regi",
)


def _looks_like_institution(text: str) -> bool:
    return text.strip().startswith(_INSTITUTION_PREFIXES) or len(text.strip()) <= 3


# vagas-2025.pdf lays specialties out in two columns; PyMuPDF's linear text
# order interleaves them, so a brand-new specialty's own heading can land
# mid-table inside the PREVIOUS specialty's institution list and get
# misread as an institution row (e.g. "Medicina de Urgência e Emergência"
# showing up as an "institution" under IMUNO-HEMOTERAPIA/Madeira). Since
# this was its first year, it also has zero colocados placements yet, so it
# never makes known_specialties on its own -- add it explicitly so any row
# correctly parsed for it isn't rejected, and so the stray row below can be
# detected and dropped instead of shown as a fake institution.
EXTRA_KNOWN_SPECIALTIES = {"Medicina de Urgência e Emergência"}


def _leaf_rows_only(parsed_rows: list) -> list:
    """Both parsers emit one row per table level (institution, region
    subtotal, specialty total) for the same seats; keep only the most
    granular level that reconciles with the specialty's own printed total.
    """
    by_specialty = defaultdict(list)
    for r in parsed_rows:
        by_specialty[r.specialty].append(r)

    out: list = []
    for group in by_specialty.values():
        total_rows = [r for r in group if not r.region]
        total = total_rows[0].seats if total_rows else None

        # MGF nests one level deeper (region -> ULS -> USF clinic), and the
        # source PDF prints BOTH a ULS's own subtotal row (e.g. "ULS Alto
        # Ave, E. P. E.") and its child USF rows (e.g. "ULS Alto Ave-USF
        # Afonso Henriques") tagged at the same "institution" level -- summing
        # them naively double-counts every ULS's seats. A ULS subtotal row's
        # name is always an exact prefix of its own children's names (up to
        # the "-"), so it can be dropped by name alone, leaving only the true
        # USF leaf rows.
        is_mgf = "geral e familiar" in (group[0].specialty or "").lower()

        with_institution = [r for r in group if r.institution]
        if is_mgf:
            # A ULS's own subtotal row carries a legal-entity suffix its USF
            # children don't ("ULS Alto Ave, E. P. E." vs. "ULS Alto Ave-USF
            # ..."), so strip that before checking the prefix relationship.
            def _uls_base(name: str) -> str:
                return re.sub(r",?\s*E\.?\s*P\.?\s*E\.?\s*$", "", name, flags=re.IGNORECASE).strip()

            names = [r.institution for r in with_institution]
            with_institution = [
                r for r in with_institution
                if not any(
                    other != r.institution
                    and re.sub(r"\s*-\s*", "-", other).startswith(re.sub(r"\s*-\s*", "-", _uls_base(r.institution)) + "-")
                    for other in names
                )
            ]
        with_region = [r for r in group if r.region and not r.institution]
        first, second = (with_institution, with_region)

        if first and (total is None or sum(r.seats for r in first) == total):
            out.extend(first)
            continue
        if second and (total is None or sum(r.seats for r in second) == total):
            out.extend(second)
            continue

        # Nothing reconciled -- prefer the printed total, else best-effort
        # the most granular breakdown (never the raw mixed-level group).
        out.extend(total_rows or with_institution or with_region)
    return out


def build_vagas(known_specialties: set[str] | None = None) -> list[dict]:
    """`known_specialties` is the closed set of real names (from colocados,
    which has no MGF nesting issue); anything else is rejected, not shipped.
    """
    rows: list[dict] = []
    rejected: set[str] = set()
    for path in sorted(RAW_VAGAS.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        if not _has_native_text(path):
            print(f"skip {path.name}: scanned PDF, no OCR-based parser yet")
            continue

        try:
            parsed = _leaf_rows_only(parse_vagas_pdf(str(path), year))
        except Exception as e:  # noqa: BLE001
            print(f"{path.name}: full parse raised ({e})")
            parsed = []

        file_rows: list[dict] = []
        for r in parsed:
            if not r.specialty or _looks_like_institution(r.specialty):
                if r.specialty:
                    rejected.add(r.specialty)
                continue
            canonical = canonicalize_specialty(r.specialty)
            if known_specialties is not None and canonical not in known_specialties:
                rejected.add(r.specialty)
                continue
            if r.institution and canonicalize_specialty(r.institution) in (known_specialties or set()) | EXTRA_KNOWN_SPECIALTIES:
                # A stray specialty heading leaked into the institution column
                # (see EXTRA_KNOWN_SPECIALTIES) -- the seat count on this row
                # can't be reliably attributed to either specialty, so drop it
                # rather than ship a fake institution.
                rejected.add(f"{r.specialty} / {r.institution} (stray heading)")
                continue
            file_rows.append(
                {
                    "year": r.year,
                    "specialty": canonical,
                    "region": r.region or "",
                    "region_key": region_key(r.region) or "",
                    "institution": r.institution or "",
                    "seats": r.seats,
                    "canonical_institution": canonicalize(r.institution) if r.institution else "",
                }
            )

        if file_rows:
            rows.extend(file_rows)
            print(f"{path.name}: {len(file_rows)}/{len(parsed)} rows kept")
        else:
            # Position-based parsing failed or rejected everything (wrong
            # indent calibration) -- fall back to the label-anchored parser.
            labeled = _leaf_rows_only(parse_vagas_labeled(str(path), year, known_specialties or set()))
            for r in labeled:
                rows.append(
                    {
                        "year": r.year,
                        "specialty": canonicalize_specialty(r.specialty),
                        "region": r.region or "",
                        "region_key": region_key(r.region) or "",
                        "institution": r.institution or "",
                        "seats": r.seats,
                        "canonical_institution": canonicalize(r.institution) if r.institution else "",
                    }
                )
            print(f"{path.name}: {len(labeled)} rows (labeled-format parser)")

    if rejected:
        print(f"rejected {len(rejected)} non-specialty labels (MGF nesting artifacts): "
              f"{sorted(rejected)[:5]}{'...' if len(rejected) > 5 else ''}")
    return rows


def build_colocados() -> list[dict]:
    rows: list[dict] = []
    ocr_paths: list[Path] = []
    # Native-text files that found 0 rows via the ruled-table parser -- some
    # years' colocados PDFs list records as plain sequential text lines with
    # no table grid, which page.find_tables() can't see at all.
    native_no_table: list[Path] = []

    for path in sorted(RAW_COLOC.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        if not _has_native_text(path):
            ocr_paths.append(path)
            print(f"skip {path.name} for now: scanned PDF, will use OCR cache if available")
            continue
        try:
            parsed = parse_colocados_pdf(str(path), year)
        except Exception as e:  # noqa: BLE001
            print(f"skip {path.name}: parse failed ({e})")
            continue
        if not parsed:
            native_no_table.append(path)
            continue
        for r in parsed:
            rows.append(
                {
                    "year": r.year,
                    "ordering_number": r.ordering_number,
                    "specialty": canonicalize_specialty(r.specialty),
                    "institution": r.institution,
                    "canonical_institution": canonicalize(r.institution),
                }
            )
        print(f"{path.name}: {len(parsed)} rows")

    # Full institution recovery only works when OCR preserves reading order
    # (true for 2025, not 2024); other years get specialty + ordering number only.
    FULL_ROW_OCR_YEARS = {2025}
    # 2024's original OCR flattened every page into one text blob, losing
    # institution entirely (see extract_colocados_ocr.py's docstring). Re-OCR'd
    # with docling's table-structure detection enabled (backend/ocr_convert.py's
    # do_table_structure flag), it comes back as real per-row markdown tables --
    # parsed by extract_colocados_ocr_table.py, no anchor/position guessing.
    TABLE_STRUCTURE_OCR_YEARS = {2024}

    known_specialties = {r["specialty"] for r in rows}
    for path in ocr_paths:
        year = int(re.search(r"20\d\d", path.name).group(0))
        ocr_md = ROOT / "data" / "processed" / "ocr_cache" / f"{path.stem}.md"

        if year in TABLE_STRUCTURE_OCR_YEARS:
            table_md = ROOT / "data" / "processed" / "ocr_cache" / f"{path.stem}-tablestruct.md"
            if not table_md.exists():
                print(f"skip {path.name}: no table-structure OCR cache yet")
                continue
            try:
                table_parsed = parse_ocr_table(str(table_md), year, known_specialties)
            except Exception as e:  # noqa: BLE001
                print(f"skip {path.name}: OCR table-structure parse failed ({e})")
                continue
            for r in table_parsed:
                rows.append(
                    {
                        "year": r.year,
                        "ordering_number": r.ordering_number,
                        "specialty": canonicalize_specialty(r.specialty),
                        "institution": r.institution,
                        "canonical_institution": canonicalize(r.institution),
                    }
                )
            print(f"{path.name}: {len(table_parsed)} rows from OCR (table-structure, with institution)")
            continue

        if not ocr_md.exists():
            print(f"skip {path.name}: no OCR cache yet, run backend/ocr_convert.py first")
            continue

        if year in FULL_ROW_OCR_YEARS:
            try:
                full_parsed = parse_ocr_colocados_full(str(ocr_md), year, known_specialties)
            except Exception as e:  # noqa: BLE001
                print(f"skip {path.name}: OCR full-row parse failed ({e})")
                continue
            for r in full_parsed:
                rows.append(
                    {
                        "year": r.year,
                        "ordering_number": r.ordering_number,
                        "specialty": canonicalize_specialty(r.specialty),
                        "institution": r.institution,
                        "canonical_institution": canonicalize(r.institution),
                    }
                )
            print(f"{path.name}: {len(full_parsed)} rows from OCR (with institution)")
            continue

        try:
            parsed = parse_ocr_colocados(str(ocr_md), year, known_specialties)
        except Exception as e:  # noqa: BLE001
            print(f"skip {path.name}: OCR parse failed ({e})")
            continue
        for r in parsed:
            rows.append(
                {
                    "year": r.year,
                    "ordering_number": r.ordering_number,
                    "specialty": canonicalize_specialty(r.specialty),
                    "institution": "",
                    "canonical_institution": "",
                }
            )
        print(f"{path.name}: {len(parsed)} rows from OCR (specialty + ordering number only)")

    # Re-run with the specialty-anchor approach now that other years have
    # populated known_specialties -- needed for full CANONICAL_MAP coverage,
    # since a lone year's own vocabulary alone (e.g. only the ~13 specialties
    # with spelling variants) would miss most uniformly-spelled specialties.
    known_specialties = {r["specialty"] for r in rows} or known_specialties
    for path in native_no_table:
        year = int(re.search(r"20\d\d", path.name).group(0))
        try:
            full_parsed = parse_colocados_native_full(str(path), year, known_specialties)
        except Exception as e:  # noqa: BLE001
            print(f"skip {path.name}: anchor-based parse failed ({e})")
            continue
        for r in full_parsed:
            rows.append(
                {
                    "year": r.year,
                    "ordering_number": r.ordering_number,
                    "specialty": canonicalize_specialty(r.specialty),
                    "institution": r.institution,
                    "canonical_institution": canonicalize(r.institution),
                }
            )
        print(f"{path.name}: {len(full_parsed)} rows (specialty-anchor parse, no ruled table)")

    rows.sort(key=lambda r: (int(r["year"]), int(r["ordering_number"])))
    return rows


def write_csv_and_json(rows: list[dict], name: str) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)

    if not rows:
        print(f"no rows for {name}, skipping write")
        return

    fieldnames = list(rows[0].keys())
    csv_path = PROCESSED / f"{name}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {csv_path} ({len(rows)} rows)")

    json_path = FRONTEND_DATA / f"{name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"wrote {json_path}")


def main() -> None:
    colocados_rows = build_colocados()
    known_specialties = {r["specialty"] for r in colocados_rows} | EXTRA_KNOWN_SPECIALTIES
    write_csv_and_json(build_vagas(known_specialties or None), "vagas")
    write_csv_and_json(colocados_rows, "colocados")


if __name__ == "__main__":
    main()
