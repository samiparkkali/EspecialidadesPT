"""Unit tests for the FastAPI endpoints in backend/api.py.

Swaps in small in-memory DataFrames instead of reading the real CSVs, so
these run regardless of whether `make process` has been run and stay fast
and deterministic.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    vagas = pd.DataFrame([
        {"specialty": "CARDIOLOGIA", "region": "Norte", "institution": "Hospital A",
         "canonical_institution": "HOSPITAL A", "year": 2024, "seats": 3},
        {"specialty": "CARDIOLOGIA", "region": "Norte", "institution": "Hospital A",
         "canonical_institution": "HOSPITAL A", "year": 2023, "seats": 2},
        {"specialty": "PEDIATRIA", "region": "Centro", "institution": "Hospital B",
         "canonical_institution": "HOSPITAL B", "year": 2024, "seats": 1},
        {"specialty": "PEDIATRIA", "region": "Centro", "institution": "",
         "canonical_institution": "", "year": 2024, "seats": 1},
    ])
    colocados = pd.DataFrame([
        {"specialty": "CARDIOLOGIA", "institution": "Hospital A",
         "canonical_institution": "HOSPITAL A", "year": 2024, "ordering_number": 100},
        {"specialty": "CARDIOLOGIA", "institution": "Hospital A",
         "canonical_institution": "HOSPITAL A", "year": 2023, "ordering_number": 150},
        {"specialty": "PEDIATRIA", "institution": "Hospital B",
         "canonical_institution": "HOSPITAL B", "year": 2024, "ordering_number": 50},
    ])
    monkeypatch.setattr(api, "vagas_df", vagas)
    monkeypatch.setattr(api, "colocados_df", colocados)
    return TestClient(api.app)


def test_list_specialties_sorted_and_deduped(client):
    resp = client.get("/api/specialties")
    assert resp.status_code == 200
    assert resp.json() == ["CARDIOLOGIA", "PEDIATRIA"]


def test_get_vagas_no_filter_returns_all_rows(client):
    resp = client.get("/api/vagas")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_get_vagas_filters_by_specialty(client):
    resp = client.get("/api/vagas", params={"specialty": "CARDIOLOGIA"})
    rows = resp.json()
    assert len(rows) == 2
    assert all(r["specialty"] == "CARDIOLOGIA" for r in rows)


def test_get_vagas_filters_by_institution_matches_either_column(client):
    resp = client.get("/api/vagas", params={"institution": "HOSPITAL A"})
    rows = resp.json()
    assert len(rows) == 2
    assert all(r["canonical_institution"] == "HOSPITAL A" for r in rows)


def test_get_vagas_filters_by_year(client):
    resp = client.get("/api/vagas", params={"year": 2023})
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["year"] == 2023


def test_vagas_evolution_excludes_region_only_rows(client):
    resp = client.get("/api/vagas/evolution", params={"specialty": "PEDIATRIA"})
    rows = resp.json()
    # Only the institution-level Pediatria row (seats=1) should count, not
    # the region-only aggregate row (also seats=1) -- otherwise seats double.
    assert rows == [{"year": 2024, "seats": 1}]


def test_vagas_evolution_sums_seats_per_year(client):
    resp = client.get("/api/vagas/evolution", params={"specialty": "CARDIOLOGIA"})
    rows = {r["year"]: r["seats"] for r in resp.json()}
    assert rows == {2023: 2, 2024: 3}


def test_get_colocados_filters_by_specialty(client):
    resp = client.get("/api/colocados", params={"specialty": "PEDIATRIA"})
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["ordering_number"] == 50


def test_get_cutoffs_reports_worst_placed_per_year(client):
    resp = client.get("/api/cutoffs", params={"specialty": "CARDIOLOGIA"})
    rows = resp.json()
    assert len(rows) == 2
    by_year = {r["year"]: r["last_ordering_number"] for r in rows}
    assert by_year == {2023: 150, 2024: 100}


def test_predict_includes_years_that_would_have_qualified(client):
    resp = client.get("/api/predict", params={"ordering_number": 120})
    results = resp.json()
    cardio = next(r for r in results if r["specialty"] == "CARDIOLOGIA")
    # 120 would have placed in 2023 (cutoff 150) but not 2024 (cutoff 100).
    assert cardio["eligible_years"] == [2023]
    assert cardio["total_years"] == 2


def test_predict_excludes_specialty_with_no_eligible_years(client):
    # A worse (higher) ordering number than every cutoff in the fixture
    # (highest is 150) qualifies for nothing.
    resp = client.get("/api/predict", params={"ordering_number": 1000})
    specialties = {r["specialty"] for r in resp.json()}
    assert specialties == set()


def test_predict_low_ordering_number_qualifies_everywhere(client):
    # A very good (low) ordering number beats every cutoff in the fixture.
    resp = client.get("/api/predict", params={"ordering_number": 10})
    cardio = next(r for r in resp.json() if r["specialty"] == "CARDIOLOGIA")
    assert cardio["eligible_years"] == [2023, 2024]


def test_predict_requires_positive_ordering_number(client):
    resp = client.get("/api/predict", params={"ordering_number": 0})
    assert resp.status_code == 422


def test_health_reports_row_counts_and_years(client):
    resp = client.get("/api/health")
    body = resp.json()
    assert body["vagas_rows"] == 4
    assert body["colocados_rows"] == 3
    assert body["vagas_years"] == [2023, 2024]
    assert body["colocados_years"] == [2023, 2024]


def test_health_handles_empty_dataframes(monkeypatch):
    monkeypatch.setattr(api, "vagas_df", pd.DataFrame())
    monkeypatch.setattr(api, "colocados_df", pd.DataFrame())
    client = TestClient(api.app)
    resp = client.get("/api/health")
    assert resp.json() == {
        "vagas_rows": 0,
        "colocados_rows": 0,
        "vagas_years": [],
        "colocados_years": [],
    }


def test_predict_returns_empty_list_when_colocados_empty(monkeypatch):
    monkeypatch.setattr(api, "colocados_df", pd.DataFrame())
    client = TestClient(api.app)
    resp = client.get("/api/predict", params={"ordering_number": 100})
    assert resp.json() == []
