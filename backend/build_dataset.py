"""Run the full extraction pipeline: PDFs -> data/processed/*.csv -> frontend/public/data/*.json.

Parses every vagas-*.pdf / *-colocados.pdf (or *-colocações.pdf) it can:
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
from pathlib import Path

import fitz

from extract_colocados import parse_colocados_pdf
from extract_colocados_ocr import parse_ocr_colocados
from extract_vagas import parse_vagas_pdf
from extract_vagas_totals import parse_specialty_totals
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


# "Specialty" values that are actually leaked clinic/institution names from
# Medicina Geral e Familiar's 4th nesting level (see extract_vagas.py's
# docstring) always start with one of these -- unlike a whitelist of exact
# specialty names, this is robust to specialty names being spelled/worded
# slightly differently across years (e.g. "Angiologia e Cirurgia Vascular"
# vs "Angiologia/cirurgia Vascular").
_INSTITUTION_PREFIXES = (
    "USF ", "UCSP ", "ULS ", "ULS", "ACES ", "Aces ", "Administra",
    "Hospital ", "Centro ", "Instituto ", "Unidade ", "Regi",
)


def _looks_like_institution(text: str) -> bool:
    return text.strip().startswith(_INSTITUTION_PREFIXES) or len(text.strip()) <= 3


def build_vagas(known_specialties: set[str] | None = None) -> list[dict]:
    """`known_specialties` (already run through canonicalize_specialty) is
    the closed set of real specialty names -- anything else, prefix-like or
    not (e.g. "Moncorvo", "Cacém", town/clinic name fragments that don't
    start with a recognizable institution prefix), gets rejected instead of
    silently shipped as a fake "specialty". Built from the cleanly-parsed
    colocados data (see main()), which doesn't have the MGF nesting
    problem vagas parsing does.
    """
    rows: list[dict] = []
    rejected: set[str] = set()
    for path in sorted(RAW_VAGAS.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        if not _has_native_text(path):
            print(f"skip {path.name}: scanned PDF, no OCR-based parser yet")
            continue

        try:
            parsed = parse_vagas_pdf(str(path), year)
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
            # Either parse_vagas_pdf raised, or it ran but every row got
            # rejected (e.g. wrong indent calibration for that year's
            # layout -- see extract_vagas.py). Either way, fall back to
            # specialty-level totals only (extract_vagas_totals.py), which
            # uses explicit "Total da Especialidade" labels instead of
            # position-based row matching.
            totals = parse_specialty_totals(str(path), year, known_specialties or set())
            for t in totals:
                rows.append(
                    {
                        "year": t.year,
                        "specialty": t.specialty,
                        "region": "",
                        "region_key": "",
                        "institution": "",
                        "seats": t.seats,
                        "canonical_institution": "",
                    }
                )
            print(f"{path.name}: {len(totals)} specialty-level totals (no institution breakdown)")

    if rejected:
        print(f"rejected {len(rejected)} non-specialty labels (MGF nesting artifacts): "
              f"{sorted(rejected)[:5]}{'...' if len(rejected) > 5 else ''}")
    return rows


def build_colocados() -> list[dict]:
    rows: list[dict] = []
    ocr_paths: list[Path] = []

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

    # OCR'd files: only specialty + ordering number are recoverable (see
    # extract_colocados_ocr.py's docstring), institution is left blank.
    # Needs the native-text years' clean specialty set as a reference, so
    # this runs after the loop above rather than year-by-year.
    known_specialties = {r["specialty"] for r in rows}
    for path in ocr_paths:
        year = int(re.search(r"20\d\d", path.name).group(0))
        ocr_md = ROOT / "data" / "processed" / "ocr_cache" / f"{path.stem}.md"
        if not ocr_md.exists():
            print(f"skip {path.name}: no OCR cache yet, run backend/ocr_convert.py first")
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
                    "specialty": r.specialty,
                    "institution": "",
                    "canonical_institution": "",
                }
            )
        print(f"{path.name}: {len(parsed)} rows from OCR (specialty + ordering number only)")

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
    known_specialties = {r["specialty"] for r in colocados_rows}
    write_csv_and_json(build_vagas(known_specialties or None), "vagas")
    write_csv_and_json(colocados_rows, "colocados")


if __name__ == "__main__":
    main()
