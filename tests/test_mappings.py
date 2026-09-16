"""Unit tests for the normalization helpers (no PDFs involved)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from institution_mapping import canonicalize  # noqa: E402
from region_mapping import region_key  # noqa: E402
from specialty_mapping import canonicalize_specialty  # noqa: E402


def test_canonicalize_maps_epe_hospital_to_uls():
    assert canonicalize("Centro Hospitalar Universitário de São João, E.P.E.") == "ULS SÃO JOÃO"


def test_canonicalize_is_uppercase():
    # Roman numerals in raw names (e.g. "Tâmega Ii") must read as the
    # numeral, not get title-cased into something misleading -- plain
    # .upper() handles that correctly.
    assert canonicalize("some clinic Ii") == "SOME CLINIC II"


def test_canonicalize_passes_through_unknown_institution_uppercased():
    assert canonicalize("Some Random Clinic") == "SOME RANDOM CLINIC"


def test_canonicalize_empty_string():
    assert canonicalize("") == ""


def test_canonicalize_specialty_normalizes_wording_variants():
    assert (
        canonicalize_specialty("Angiologia/cirurgia Vascular")
        == canonicalize_specialty("Angiologia e Cirurgia Vascular")
    )


def test_canonicalize_specialty_passthrough_for_unmapped():
    assert canonicalize_specialty("Not A Real Specialty") == "Not A Real Specialty"


def test_region_key_matches_all_seven_regions():
    cases = {
        "Administração Regional de Saúde do Norte, I.P.": "norte",
        "Administração Regional de Saúde do Centro, I.P.": "centro",
        "Administração Regional de Saúde de Lisboa e Vale do Tejo, I.P.": "lisboa-vale-tejo",
        "Administração Regional de Saúde do Alentejo, I.P.": "alentejo",
        "Administração Regional de Saúde do Algarve, I.P.": "algarve",
        "Região Autónoma dos Açores": "acores",
        "Região Autónoma da Madeira": "madeira",
    }
    for raw, expected in cases.items():
        assert region_key(raw) == expected, raw


def test_region_key_unknown_returns_none():
    assert region_key("Some Unrelated Text") is None


def test_region_key_empty_returns_none():
    assert region_key("") is None
