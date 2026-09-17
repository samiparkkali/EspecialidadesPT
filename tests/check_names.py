"""Flags specialty/institution names that look suspicious, for human
review -- NOT a pass/fail test. Judging whether a flagged name is a
genuine data issue (extraction artifact, typo, an unmerged duplicate of
something already in institution_mapping.py) or just a normal small
institution needs a person who knows the domain; this surfaces candidates
instead of guessing.

Run: python tests/check_names.py
Writes: data/processed/QA_FLAGS.md
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

VAGAS_CSV = ROOT / "data" / "processed" / "vagas.csv"
COLOCADOS_CSV = ROOT / "data" / "processed" / "colocados.csv"
OUT_PATH = ROOT / "data" / "processed" / "QA_FLAGS.md"

# Absence of these is only suspicious for a *long* name; a short name lacking
# one is more likely a leaked fragment than a genuine institution.
_LEGAL_SUFFIXES = ("E.P.E", "I.P.", "ULS", "ARS", "SESARAM", "SRS")


def _looks_suspicious_institution(name: str) -> bool:
    words = name.split()
    if len(words) <= 2 and not any(suf in name for suf in _LEGAL_SUFFIXES):
        return True  # e.g. a bare place/clinic fragment, no legal suffix
    if re.search(r"\d", name):
        return True  # digits in an institution name are almost always noise
    return False


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def flag_institutions(rows: list[dict]) -> Counter:
    flagged: Counter[str] = Counter()
    for r in rows:
        raw = r.get("institution", "").strip()
        if raw and _looks_suspicious_institution(raw):
            flagged[raw] += 1
    return flagged


def flag_specialties(rows: list[dict], known_specialties: set[str]) -> Counter:
    flagged: Counter[str] = Counter()
    for r in rows:
        raw = r.get("specialty", "").strip()
        if raw and raw not in known_specialties:
            flagged[raw] += 1
    return flagged


def main() -> None:
    vagas_rows = _read_csv(VAGAS_CSV)
    colocados_rows = _read_csv(COLOCADOS_CSV)

    # colocados.csv's specialty column is the trustworthy reference (parsed
    # via table finder, no indent-hierarchy guessing).
    known_specialties = {r["specialty"] for r in colocados_rows}

    inst_flags = flag_institutions(vagas_rows) + flag_institutions(colocados_rows)
    spec_flags = flag_specialties(vagas_rows, known_specialties)

    lines = [
        "# QA flags: names that look suspicious",
        "",
        "Not necessarily wrong, just worth a human glance. Regenerate with",
        "`python tests/check_names.py` after re-running `make process`.",
        "",
        f"## Institutions ({len(inst_flags)} distinct, short/no legal-suffix or contain digits)",
        "",
    ]
    for name, count in inst_flags.most_common():
        lines.append(f"- ({count}x) {name}")

    lines += [
        "",
        f"## Specialties ({len(spec_flags)} distinct, not in colocados.csv's reference set)",
        "",
    ]
    for name, count in spec_flags.most_common():
        lines.append(f"- ({count}x) {name}")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(inst_flags)} institutions, {len(spec_flags)} specialties flagged")


if __name__ == "__main__":
    main()
