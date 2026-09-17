"""Renders the three canonicalization hierarchies (specialty, institution,
region) into one readable Markdown reference under data/processed/markdown/,
so "which raw names belong to this canonical name" can be consulted/audited
without reading Python source.

Specialties/institutions/regions each have a curated CANONICAL_MAP /
REGION_KEYS dict (source of truth for matching), but institutions and
regions also pick up raw spellings never explicitly listed there via
substring/fallback rules (e.g. institution_mapping.py's clinic-suffix rule).
So for those two, this cross-references the curated dict against every raw
value actually observed in vagas.csv/colocados.csv (both keep the raw value
alongside its canonical form) to get the true, complete picture -- not just
what's hardcoded. Specialty raw values aren't kept in the CSVs (only the
canonical form is written), so that section reflects CANONICAL_MAP only.

Run after build_dataset.py: python backend/build_hierarchy.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
VAGAS_CSV = ROOT / "data" / "processed" / "vagas.csv"
COLOCADOS_CSV = ROOT / "data" / "processed" / "colocados.csv"
OUT_PATH = ROOT / "data" / "processed" / "markdown" / "hierarchy.md"


def _read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_specialty_section() -> list[str]:
    from specialty_mapping import CANONICAL_MAP

    vagas_specialties = {r["specialty"] for r in _read_rows(VAGAS_CSV)}
    colocados_specialties = {r["specialty"] for r in _read_rows(COLOCADOS_CSV)}
    all_specialties = sorted(vagas_specialties | colocados_specialties)

    lines = ["## Specialties", "", (
        "Curated variant list (`backend/specialty_mapping.py`'s `CANONICAL_MAP`) "
        "plus every canonical specialty name that actually appears in the data. "
        "Raw pre-canonicalization spellings aren't kept in the CSVs, so a "
        "specialty with no listed variants below either only ever appears with "
        "one consistent spelling, or is matched via the generic "
        "punctuation/connector-word normalization instead of an explicit variant."
    ), ""]

    variants_by_canonical: dict[str, list[str]] = defaultdict(list)
    for canonical, variants in CANONICAL_MAP.items():
        variants_by_canonical[canonical.upper()].extend(variants)

    for specialty in all_specialties:
        variants = sorted(set(variants_by_canonical.get(specialty, [])))
        if variants:
            lines.append(f"- **{specialty}**: {', '.join(variants)}")
        else:
            lines.append(f"- **{specialty}**")
    lines.append("")
    return lines


def build_institution_section() -> list[str]:
    rows = _read_rows(VAGAS_CSV) + _read_rows(COLOCADOS_CSV)
    variants_by_canonical: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        if r["institution"] and r["canonical_institution"]:
            variants_by_canonical[r["canonical_institution"]].add(r["institution"])

    lines = ["## Institutions", "", (
        "Every canonical institution name observed in vagas.csv/colocados.csv, "
        "with every distinct raw spelling that canonicalized to it (from "
        "`backend/institution_mapping.py`'s `CANONICAL_MAP` plus its "
        "slash-spacing and USF/UCSP/USP/UCC clinic-suffix fallback rules). A "
        "canonical name with 2+ listed variants is a real reconciliation the "
        "code is doing across years/spellings -- worth spot-checking that "
        "they're genuinely the same institution."
    ), ""]

    for canonical in sorted(variants_by_canonical):
        variants = sorted(variants_by_canonical[canonical])
        if len(variants) == 1 and variants[0].upper() == canonical:
            continue  # no real reconciliation happening, just a pass-through
        lines.append(f"- **{canonical}**")
        for v in variants:
            lines.append(f"  - {v}")
    lines.append("")
    return lines


def build_region_section() -> list[str]:
    from region_mapping import REGION_KEYS

    rows = _read_rows(VAGAS_CSV)
    variants_by_key: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        if r["region"] and r["region_key"]:
            variants_by_key[r["region_key"]].add(r["region"])

    lines = ["## Regions", "", (
        "Every raw region string observed in vagas.csv grouped by its short "
        "map key (`backend/region_mapping.py`'s `REGION_KEYS`)."
    ), ""]

    for key in sorted(set(REGION_KEYS) | set(variants_by_key)):
        observed = sorted(variants_by_key.get(key, []))
        lines.append(f"- **{key}** (matches: {', '.join(REGION_KEYS.get(key, []))})")
        for v in observed:
            lines.append(f"  - {v}")
    lines.append("")
    return lines


def build() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Canonicalization hierarchy: specialties, institutions, regions",
        "",
        "Reference for which raw names collapse into which canonical name. "
        "Regenerate with `python backend/build_hierarchy.py` after "
        "`build_dataset.py`.",
        "",
    ]
    lines += build_specialty_section()
    lines += build_institution_section()
    lines += build_region_section()
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
