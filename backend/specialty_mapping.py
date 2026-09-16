"""Maps raw specialty names to a canonical form for cross-year analysis.

Specialty names are worded slightly differently across years' PDFs (e.g.
"Angiologia e Cirurgia Vascular" vs "Angiologia/cirurgia Vascular",
"Endocrinologia/Nutrição" vs "Endocrinologia E Nutrição") -- without
normalizing, the same specialty shows up as two separate rows/filter
options depending on which year's file it came from.

Also includes "Medicina de Emergência", a specialty added to the Internato
Médico list more recently (not yet observed in the years currently
parsed -- see CLAUDE.md's per-year-format note) so it's ready to match
once a parser exists for those years, instead of silently being treated
as an unknown/unmapped specialty when it first appears.

Like institution_mapping.py, this is best-effort and extensible: run
`python backend/specialty_mapping.py data/processed/vagas.csv` to list
any specialty names that don't match a known canonical entry.
"""

from __future__ import annotations

import re

# canonical_name -> list of raw-name variants (case-insensitive) that map to it.
CANONICAL_MAP: dict[str, list[str]] = {
    "Angiologia e Cirurgia Vascular": [
        "Angiologia e Cirurgia Vascular",
        "Angiologia/cirurgia Vascular",
        "Angiologia / Cirurgia Vascular",
    ],
    "Endocrinologia e Nutrição": [
        "Endocrinologia e Nutrição",
        "Endocrinologia/nutrição",
        "Endocrinologia / Nutrição",
    ],
    "Ginecologia e Obstetrícia": [
        "Ginecologia e Obstetrícia",
        "Ginecologia / Obstetrícia",
        "Ginecologia/obstetrícia",
    ],
    "Medicina Física e de Reabilitação": [
        "Medicina Física e de Reabilitação",
        "Medicina Física E De Reabilitação",
    ],
    "Medicina Geral e Familiar": [
        "Medicina Geral e Familiar",
        "Medicina Geral E Familiar",
    ],
    "Medicina do Trabalho": [
        "Medicina do Trabalho",
        "Medicina Do Trabalho",
    ],
    "Psiquiatria da Infância e da Adolescência": [
        "Psiquiatria da Infância e da Adolescência",
        "Psiquiatria Da Infância E Da Adolescência",
    ],
    "Cirurgia Plástica, Reconstrutiva e Estética": [
        "Cirurgia Plástica Reconstrutiva Estética",
        "Cirurgia Plástica, Reconstrutiva E Estética",
    ],
    "Oncologia Médica": ["Oncologia Médica"],
    "Radioncologia": ["Radioncologia", "Radioterapia"],
    # Not yet seen in the years currently parsed (2022 fails to parse,
    # 2024/2025 need OCR) -- kept here so it matches immediately once one
    # of those years is added, per the "added last year" note.
    "Medicina de Emergência": [
        "Medicina de Emergência",
        "Medicina De Emergência",
    ],
}


def canonicalize_specialty(raw_specialty: str) -> str:
    """Best-effort canonical name; falls back to the raw name (title-cased
    for consistent display) if no mapping matches."""
    if not raw_specialty:
        return raw_specialty
    for canonical, variants in CANONICAL_MAP.items():
        for variant in variants:
            if raw_specialty.strip().lower() == variant.lower():
                return canonical
    return raw_specialty.strip()


if __name__ == "__main__":
    import csv
    import sys
    from collections import Counter

    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/vagas.csv"
    unmapped: Counter[str] = Counter()
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            spec = row.get("specialty", "")
            if spec and canonicalize_specialty(spec) == spec.strip():
                # Still "unmapped" in the sense that it fell through to the
                # raw-name fallback rather than matching a known variant --
                # only worth flagging if it's suspiciously similar to
                # something already in CANONICAL_MAP (manual review).
                unmapped[spec.strip()] += 1

    print(f"{len(unmapped)} distinct specialties passed through unchanged "
          f"(not necessarily wrong -- just not aliased to anything):")
    for name, count in unmapped.most_common(60):
        print(f"  {count:4d}  {name}")
