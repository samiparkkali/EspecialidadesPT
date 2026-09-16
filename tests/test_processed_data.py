"""Structural invariants on the generated CSVs (skipped if not built yet --
run `make process` first). Hard failures here mean something is genuinely
broken (wrong types, out-of-range years, known-bad artifacts creeping back
in); the softer "flag for human review" checks live in check_names.py
instead, since those need a person's judgment call, not a pass/fail.
"""

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VAGAS_CSV = ROOT / "data" / "processed" / "vagas.csv"
COLOCADOS_CSV = ROOT / "data" / "processed" / "colocados.csv"

# Confirmed-bad specialty values from earlier bugs (MGF's extra nesting
# level leaking clinic/town names as fake specialties) -- regression guard,
# not exhaustive, see check_names.py for open-ended review.
KNOWN_BAD_SPECIALTIES = {
    "Moncorvo", "Cacém", "Madeir", "Queirós", "Santiago", "Caravela",
    "Dunas", "Infesta", "Oceanos", "Lagoa", "Mogadouro", "Eanes",
    "Pescadores", "N.º",
}

VALID_YEARS = range(2021, 2026)
VALID_REGION_KEYS = {
    "", "norte", "centro", "lisboa-vale-tejo", "alentejo", "algarve",
    "acores", "madeira",
}


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        pytest.skip(f"{path.name} not built yet -- run `make process` first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_vagas_has_no_known_bad_specialties():
    rows = _read_csv(VAGAS_CSV)
    bad = {r["specialty"] for r in rows} & KNOWN_BAD_SPECIALTIES
    assert not bad, f"known-bad specialty names leaked back in: {bad}"


def test_vagas_seats_are_positive_integers():
    rows = _read_csv(VAGAS_CSV)
    for r in rows:
        assert int(r["seats"]) > 0, r


def test_vagas_years_in_range():
    rows = _read_csv(VAGAS_CSV)
    for r in rows:
        assert int(r["year"]) in VALID_YEARS, r


def test_vagas_region_key_is_known():
    rows = _read_csv(VAGAS_CSV)
    for r in rows:
        assert r["region_key"] in VALID_REGION_KEYS, r


def test_vagas_institution_rows_have_region():
    """A row with an institution should also have its region filled in
    (institution-level rows always come from a region block)."""
    rows = _read_csv(VAGAS_CSV)
    for r in rows:
        if r["institution"]:
            assert r["region"], f"institution row missing region: {r}"


def test_colocados_ordering_numbers_are_positive():
    rows = _read_csv(COLOCADOS_CSV)
    for r in rows:
        assert int(r["ordering_number"]) > 0, r


def test_colocados_years_in_range():
    rows = _read_csv(COLOCADOS_CSV)
    for r in rows:
        assert int(r["year"]) in VALID_YEARS, r


def test_colocados_has_specialty():
    rows = _read_csv(COLOCADOS_CSV)
    for r in rows:
        assert r["specialty"], r


def test_colocados_institution_present_for_native_years_only():
    """OCR-derived years (extract_colocados_ocr.py) only recover specialty
    + ordering number, institution is intentionally blank -- see its
    docstring. Native-text years should always have one."""
    rows = _read_csv(COLOCADOS_CSV)
    for r in rows:
        if int(r["year"]) not in (2024, 2025):
            assert r["institution"], r
