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
from vagas_corrections import apply_corrections
from colocados_corrections import apply_corrections as apply_colocados_corrections
from log_utils import get_logger

logger = get_logger(__name__)

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


# Catches MGF's 4th-nesting-level clinic names that leak in as fake "specialty" rows.
_INSTITUTION_PREFIXES = (
    "USF ", "UCSP ", "ULS ", "ULS", "ACES ", "Aces ", "Administra",
    "Hospital ", "Centro ", "Instituto ", "Unidade ", "Regi",
)


def _looks_like_institution(text: str) -> bool:
    return text.strip().startswith(_INSTITUTION_PREFIXES) or len(text.strip()) <= 3


# vagas-2025.pdf's two-column layout can misread this new specialty's own
# heading as a fake institution row inside the previous specialty's list;
# since it's brand new it has no colocados placements yet to auto-populate
# known_specialties, so it's added explicitly to avoid rejecting it.
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

        # MGF's PDF rows print both a ULS's own subtotal row and its child USF
        # rows at the same "institution" level; summing both double-counts
        # seats, so subtotal rows (an exact name prefix of their children's,
        # up to "-") are dropped below, keeping only true USF leaf rows.
        is_mgf = "geral e familiar" in (group[0].specialty or "").lower()

        with_institution = [r for r in group if r.institution]
        if is_mgf:
            # Strip the subtotal row's legal-entity suffix before prefix-matching.
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

        # Neither breakdown reconciled with the printed total -- ship whatever
        # we have, but flag it since this is exactly the case this function
        # exists to catch (parser misattribution silently over/under-counting
        # a specialty's seats).
        if total is not None and (with_institution or with_region):
            logger.warning(
                "_leaf_rows_only: %s seats don't reconcile with printed total %d "
                "(institution sum=%s, region sum=%s) -- shipping the most granular breakdown anyway",
                group[0].specialty, total,
                sum(r.seats for r in with_institution) if with_institution else None,
                sum(r.seats for r in with_region) if with_region else None,
            )

        # Prefer the printed total, else the most granular breakdown available.
        out.extend(total_rows or with_institution or with_region)
    return out


def build_vagas(known_specialties: set[str] | None = None) -> list[dict]:
    """`known_specialties` is the closed set of real names (from colocados,
    which has no MGF nesting issue); anything else is rejected, not shipped.
    """
    rows: list[dict] = []
    rejected: set[str] = set()
    # Declarações de Retificação are small hand-typed diffs (vagas_corrections.py),
    # not full tables in the regular per-year format -- skip parsing them here.
    for path in sorted(p for p in RAW_VAGAS.glob("*.pdf") if not p.name.lower().startswith("declaracao")):
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
                # Stray specialty heading leaked into the institution column; drop
                # rather than ship a fake institution (see EXTRA_KNOWN_SPECIALTIES).
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
    return apply_corrections(rows)


def build_colocados() -> list[dict]:
    rows: list[dict] = []
    ocr_paths: list[Path] = []
    # Native-text files with 0 rows: some years list records as plain text
    # lines with no table grid, invisible to page.find_tables().
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

    # Full institution recovery needs OCR to preserve reading order (2025 only).
    FULL_ROW_OCR_YEARS = {2025}
    # 2024's OCR flattened pages into one blob, losing institution (see
    # extract_colocados_ocr.py); re-OCR'd with table-structure detection gives
    # real per-row markdown tables instead (extract_colocados_ocr_table.py).
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

    # Re-run with other years' known_specialties now populated -- a single
    # year's own vocabulary alone would miss most uniformly-spelled specialties.
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

    rows = apply_colocados_corrections(rows)
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
