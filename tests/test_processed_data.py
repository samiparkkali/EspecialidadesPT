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
    "MONCORVO", "CACÉM", "MADEIR", "QUEIRÓS", "SANTIAGO", "CARAVELA",
    "DUNAS", "INFESTA", "OCEANOS", "LAGOA", "MOGADOURO", "EANES",
    "PESCADORES", "N.º",
}

VALID_YEARS = range(2021, 2026)
VALID_REGION_KEYS = {
    "", "norte", "centro", "lisboa-vale-tejo", "alentejo", "algarve",
    "acores", "madeira",
}

# Each vagas-YYYY.pdf prints its own grand total ("Total Geral" 2023-2025,
# "Total Nacional" 2021-2022) -- the one number in the whole pipeline that's
# ACSS's own, not derived. Summing vagas.csv's seats per year must land
# within a few seats of it (institution-vs-region rounding, not a parser
# regression) -- see notebooks/01_qa_seats_by_year_location.ipynb and
# build_dataset.py's _leaf_rows_only for why this used to be off by ~3x.
OFFICIAL_TOTAL_SEATS = {2021: 1938, 2022: 2054, 2023: 2248, 2024: 2165, 2025: 2330}
OFFICIAL_TOTAL_TOLERANCE = 200


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        pytest.skip(f"{path.name} not built yet -- run `make process` first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_vagas_has_no_known_bad_specialties():
    rows = _read_csv(VAGAS_CSV)
    bad = {r["specialty"] for r in rows} & KNOWN_BAD_SPECIALTIES
    assert not bad, f"known-bad specialty names leaked back in: {bad}"


def test_vagas_seats_are_non_negative_integers():
    """0 is a legitimate value (a region/institution offered no seats for
    that specialty that year); negative would indicate a parsing bug."""
    rows = _read_csv(VAGAS_CSV)
    for r in rows:
        assert int(r["seats"]) >= 0, r


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


def test_colocados_has_no_seats_column():
    """Seat counts only ever come from vagas.csv -- colocados counts
    placements, which is routinely lower than seats offered (unfilled
    vacancies are normal, see CLAUDE.md). A "seats" column here would
    invite someone to sum/chart it as if it were capacity."""
    rows = _read_csv(COLOCADOS_CSV)
    assert "seats" not in rows[0]


def test_colocados_has_specialty():
    rows = _read_csv(COLOCADOS_CSV)
    for r in rows:
        assert r["specialty"], r


def test_vagas_total_seats_matches_official_grand_total_per_year():
    rows = _read_csv(VAGAS_CSV)
    totals: dict[int, int] = {}
    for r in rows:
        year = int(r["year"])
        totals[year] = totals.get(year, 0) + int(r["seats"])
    for year, official in OFFICIAL_TOTAL_SEATS.items():
        got = totals.get(year, 0)
        assert abs(got - official) <= OFFICIAL_TOTAL_TOLERANCE, (
            f"{year}: got {got}, official grand total is {official} "
            f"(diff {got - official}, tolerance {OFFICIAL_TOTAL_TOLERANCE})"
        )


def test_colocados_institution_blank_only_for_2024():
    """2024's OCR text scrambles institution names across records (see
    extract_colocados_ocr_full.py's docstring), so institution is
    intentionally left blank for it. Every other year (native-text, or
    2025's OCR which preserves row order) should always have one."""
    rows = _read_csv(COLOCADOS_CSV)
    for r in rows:
        if int(r["year"]) != 2024:
            assert r["institution"], r
