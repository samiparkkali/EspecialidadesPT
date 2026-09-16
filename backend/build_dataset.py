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
from extract_vagas import parse_vagas_pdf
from institution_mapping import canonicalize
from specialty_mapping import canonicalize_specialty

ROOT = Path(__file__).resolve().parent.parent
RAW_VAGAS = ROOT / "data" / "raw" / "vagas"
RAW_COLOC = ROOT / "data" / "raw" / "colocacoes"
PROCESSED = ROOT / "data" / "processed"
FRONTEND_DATA = ROOT / "frontend" / "public" / "data"


def _has_native_text(path: Path) -> bool:
    doc = fitz.open(path)
    for i in range(min(5, doc.page_count)):
        if len(doc[i].get_text().strip()) > 50:
            return True
    return False


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


def build_vagas() -> list[dict]:
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
            print(f"skip {path.name}: parse failed ({e})")
            continue
        kept = 0
        for r in parsed:
            if not r.specialty or _looks_like_institution(r.specialty):
                if r.specialty:
                    rejected.add(r.specialty)
                continue
            kept += 1
            rows.append(
                {
                    "year": r.year,
                    "specialty": canonicalize_specialty(r.specialty),
                    "region": r.region or "",
                    "institution": r.institution or "",
                    "seats": r.seats,
                    "canonical_institution": canonicalize(r.institution) if r.institution else "",
                }
            )
        print(f"{path.name}: {kept}/{len(parsed)} rows kept")
    if rejected:
        print(f"rejected {len(rejected)} non-specialty labels (MGF nesting artifacts): "
              f"{sorted(rejected)[:5]}{'...' if len(rejected) > 5 else ''}")
    return rows


def build_colocados() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(RAW_COLOC.glob("*.pdf")):
        year = int(re.search(r"20\d\d", path.name).group(0))
        if not _has_native_text(path):
            print(f"skip {path.name}: scanned PDF, no OCR-based parser yet")
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
    write_csv_and_json(build_vagas(), "vagas")
    write_csv_and_json(build_colocados(), "colocados")


if __name__ == "__main__":
    main()
