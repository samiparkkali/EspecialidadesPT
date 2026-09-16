"""Maps raw institution names to a canonical identity for cross-year analysis.

Portugal's SNS reorganized in 2024/2025: hospitals and their local primary
care clusters (previously separate "Centro Hospitalar X, E.P.E." and
"ACES Y" entities) were merged into single "ULS <region>" (Unidade Local de
Saude) entities. Without this mapping, the same physical hospital looks
like a brand new institution starting in 2025, breaking any seat/placement
evolution trend across years.

This is a best-effort, manually curated table built from the institution
names actually observed in the 2023 and 2025 extracted data (see
data/processed/vagas.csv) -- it is NOT an exhaustive list of every merger.
Extend CANONICAL_MAP as more raw name variants turn up (run
`python backend/institution_mapping.py data/processed/vagas.csv` to list
any institution names that don't match a known canonical entry, so gaps
here are visible rather than silently mis-grouped).

The raw name is always kept alongside the canonical one in processed data
(never overwritten) -- this mapping only adds a `canonical_institution`
column for grouping/charting, per CLAUDE.md's "keep source columns"
guidance.
"""

from __future__ import annotations

import re

# canonical_name -> list of raw-name substrings (case-insensitive) that map to it.
# Order matters: first match wins, so put more specific patterns first.
CANONICAL_MAP: dict[str, list[str]] = {
    "ULS São João": [
        "Centro Hospitalar Universitário de São João",
        "ULS São João",
        "ULS de São João",
    ],
    "ULS Santo António": [
        "Centro Hospitalar Universitário de Santo António",
        "ULS Santo António",
        "ULS de Santo António",
    ],
    "ULS Santa Maria": [
        "Centro Hospitalar Universitário de Lisboa Norte",
        "ULS Santa Maria",
        "ULS de Santa Maria",
    ],
    "ULS São José": [
        "Centro Hospitalar Universitário Lisboa Central",
        "Centro Hospitalar Universitário de Lisboa Central",
        "ULS São José",
        "ULS de São José",
    ],
    "ULS Coimbra": [
        "Centro Hospitalar e Universitário de Coimbra",
        "ULS Coimbra",
        "ULS de Coimbra",
    ],
    "ULS Braga": [
        "Hospital de Braga",
        "ULS Braga",
        "ULS de Braga",
    ],
    "ULS Gaia/Espinho": [
        "Centro Hospitalar Vila Nova de Gaia/Espinho",
        "ULS Gaia/Espinho",
        "ULS de Gaia/Espinho",
    ],
    "ULS Tâmega e Sousa": [
        "Centro Hospitalar do Tâmega e Sousa",
        "ULS Tâmega e Sousa",
        "ULS do Tâmega e Sousa",
    ],
    "ULS Trás-os-Montes e Alto Douro": [
        "Centro Hospitalar de Trás-os-Montes e Alto Douro",
        "ULS Trás-os-Montes",
    ],
    "ULS Almada/Seixal": [
        "Hospital Garcia de Orta",
        "ULS Almada/Seixal",
    ],
    "ULS Loures/Odivelas": [
        "Hospital Beatriz Ângelo",
        "ULS Loures/Odivelas",
    ],
    "ULS Algarve": [
        "Centro Hospitalar Universitário do Algarve",
        "ULS Algarve",
        "ULS do Algarve",
    ],
    "ULS Matosinhos": [
        "Unidade Local de Saúde de Matosinhos",
        "ULS Matosinhos",
        "ULS de Matosinhos",
    ],
}


def canonicalize(raw_institution: str) -> str:
    """Best-effort canonical name (display/filter form -- always uppercase,
    e.g. so a badly-cased "Aces Tamega Ii" reads as "... II" like the roman
    numeral it is, not title-cased into something misleading). Falls back to
    the raw name (uppercased) if no canonical mapping matches."""
    if not raw_institution:
        return raw_institution
    for canonical, patterns in CANONICAL_MAP.items():
        for pattern in patterns:
            if re.search(re.escape(pattern), raw_institution, re.IGNORECASE):
                return canonical.upper()
    return raw_institution.strip().upper()


if __name__ == "__main__":
    import csv
    import sys
    from collections import Counter

    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/vagas.csv"
    unmapped: Counter[str] = Counter()
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            inst = row.get("institution", "")
            if inst and canonicalize(inst) == inst.strip():
                unmapped[inst.strip()] += 1

    print(f"{len(unmapped)} distinct institutions with no canonical mapping "
          f"(passed through unchanged):")
    for name, count in unmapped.most_common(30):
        print(f"  {count:4d}  {name}")
