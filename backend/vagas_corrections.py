"""Manual corrections from official Declarações de Retificação published
after a year's vagas notice -- these are small, hand-typed diffs against a
correction PDF (in data/raw/vagas/), not parsed automatically, since each
one is a one-off amendment to a handful of specific rows rather than a
regular table format.
"""

from __future__ import annotations

from institution_mapping import canonicalize


def _rename(rows: list[dict], year: int, specialty: str, old_institution: str, new_institution: str) -> None:
    for r in rows:
        if r["year"] == year and r["specialty"] == specialty and r["institution"] == old_institution:
            r["institution"] = new_institution
            r["canonical_institution"] = canonicalize(new_institution)


def _set_seats(rows: list[dict], year: int, specialty: str, institution: str, seats: int) -> None:
    for r in rows:
        if r["year"] == year and r["specialty"] == specialty and r["institution"] == institution:
            r["seats"] = seats


def _remove(rows: list[dict], year: int, specialty: str, institution: str) -> None:
    rows[:] = [
        r for r in rows
        if not (r["year"] == year and r["specialty"] == specialty and r["institution"] == institution)
    ]


def apply_corrections(rows: list[dict]) -> list[dict]:
    """Applies Declaração de Retificação n.º 1050-A/2025/2 (17-11-2025),
    correcting Aviso n.º 27433-A/2025/2 (31-10-2025)'s vagas-2025 mapa."""
    rows = list(rows)

    # Cirurgia Geral 78 -> 77: ULS Algarve - Hospital de Faro 2 -> 1.
    _set_seats(rows, 2025, "CIRURGIA GERAL", "ULS Algarve — Hospital de Faro", 1)

    # Medicina Geral e Familiar 691 -> 690 (Centro 141 -> 140):
    # "UCSP Alvaiázere" renamed to "USF Alva Várzea" (same 1 seat), and
    # "ULS Guarda — UCSP Pinhel" (1 seat) dropped entirely.
    _rename(
        rows, 2025, "MEDICINA GERAL E FAMILIAR",
        "ULS Coimbra — UCSP Alvaiázere", "ULS Coimbra — USF Alva Várzea",
    )
    _remove(rows, 2025, "MEDICINA GERAL E FAMILIAR", "ULS Guarda — UCSP Pinhel")

    # Neurologia 39 -> 41 (Norte 15 -> 17): a missing "ULS Gaia/Espinho" row
    # (2 seats) was added.
    rows.append(
        {
            "year": 2025,
            "specialty": "NEUROLOGIA",
            "region": "Norte",
            "region_key": "norte",
            "institution": "ULS Gaia/Espinho",
            "seats": 2,
            "canonical_institution": canonicalize("ULS Gaia/Espinho"),
        }
    )

    # Pediatria 113 -> 114 (Alentejo 3 -> 4): ULS Alentejo Central 1 -> 2.
    _set_seats(rows, 2025, "PEDIATRIA", "ULS Alentejo Central", 2)

    return rows
