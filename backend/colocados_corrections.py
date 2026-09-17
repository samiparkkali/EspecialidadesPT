"""Hand-verified corrections for 2022 colocados ordering numbers.

`extract_colocados_native_full.py`'s anchor-based row splitting misreads a
handful of ordering numbers in the 2022 PDF (dropped/altered digits -- e.g.
a stray hyphen mid-token like "4-83" extracts as just "4"; digit-shape
misreads like "8" read as "6"). This silently produced ~19 pairs of rows
that appeared to share one ordering number, when in fact one row of each
pair had the wrong number entirely.

Each entry below was confirmed by rendering a high-resolution crop of the
actual PDF row and reading the true printed number directly, since neither
native text extraction nor RapidOCR could resolve the ambiguity on their
own. Keyed by (year, wrong ordering_number, specialty, institution) so only
the specific mis-extracted row is touched -- the other row sharing that
wrong number is untouched since its specialty/institution won't match.
"""

from __future__ import annotations

from log_utils import get_logger

logger = get_logger(__name__)

# (year, wrong_ordering_number, specialty, institution) -> correct_ordering_number
_FIXES: dict[tuple[int, int, str, str], int] = {
    (2022, 4, "MEDICINA GERAL E FAMILIAR", "Aces Douro li- Douro Sul- UsE Almedina"): 483,
    (2022, 4, "PEDIATRIA", "Hospital de Braga, E.P.E."): 485,
    (2022, 11, "PEDIATRIA", "Hospital Espírito Santo de Ëvora, EFE."): 1111,
    (2022, 24, "ANESTESIOLOGIA", "Centro Hospitalar do Baixo Vouga, EFE."): 248,
    (2022, 136, "OTORRINOLARINGOLOGIA", "Centro Hospitalar e Universitário de Coimbra, E.P.E,"): 106,
    (2022, 168, "SAÚDE PÚBLICA", "Aces do Baixo Mondego - Seder Coimbra"): 1687,
    (2022, 325, "MEDICINA GERAL E FAMILIAR", "Aces Cávado I - Braga - Usf Maxisaúde"): 725,
    (2022, 390, "PEDIATRIA", "Centro Hospitalar de Tondela - Viseu, EFE."): 790,
    (2022, 563, "MEDICINA DESPORTIVA", "de Lisboa"): 560,
    (2022, 634, "ORTOPEDIA", "Centro Hospitalar do Tâmega e Sousa, EFE."): 674,
    (2022, 768, "REUMATOLOGIA", "Centro Hospitalar e Universitário de Coimbra, EFE."): 788,
    (2022, 796, "MEDICINA NUCLEAR", "fl31ztlrt. Centro Hospitalar e Universitário de Coimbra, EFE. «iFI!"): 798,
    (2022, 889, "MEDICINA GERAL E FAMILIAR", "Aces Entre Douro e Vouga li - Aveiro Norte - Usf Calâmbriga"): 1889,
    (2022, 912, "PNEUMOLOGIA", "Hospital de Loures, E. P. E."): 812,
    (2022, 1020, "PSIQUIATRIA", "Hospital de Loures, E. P. E."): 1025,
    (2022, 1309, "MEDICINA GERAL E FAMILIAR", "Aces Grande Porto IS - Maia / Valongo- Usf Íris"): 1300,
    (2022, 1603, "ONCOLOGIA MÉDICA", "Instituto Português Oncologia de Lisboa Francisco Gentil, E.P,E."): 1803,
    (2022, 1644, "SAÚDE PÚBLICA", "Aces Cávado I - Braga"): 1844,
    (2022, 2087, "MEDICINA INTERNA", "Centro Hospitalar de Tondela . Visou, E.P.E."): 2097,
    (2022, 587, "PNEUMOLOGIA", "Hospital Prof. Dr. Fernando Fonseca, EFE."): 567,
    (2022, 765, "PSIQUIATRIA", "Centro Hospitalar do Tâmega e Sousa, E.P.E."): 766,
    (2022, 1078, "PSIQUIATRIA", "da Infância e da Adolescéncia Centro Hospitalar Universitário de Lisboa Norte, E. P. E."): 1079,
    (2022, 1145, "MEDICINA DO TRABALHO", "Centro Hospitalar e Universitário de Coimbra, EFE."): 1148,
    (2022, 1525, "MEDICINA INTERNA", "Centro Hospitalar do Médio Ave, E.P.E."): 1325,
}


def apply_corrections(rows: list[dict]) -> list[dict]:
    remaining = dict(_FIXES)
    applied = 0
    for r in rows:
        key = (int(r["year"]), int(r["ordering_number"]), r["specialty"], r["institution"])
        if key in remaining:
            correct = remaining.pop(key)
            logger.info(
                "colocados: %s/%s/%s ordering_number %s -> %s",
                key[0], key[2], key[3], key[1], correct,
            )
            r["ordering_number"] = correct
            applied += 1
    logger.info("colocados_corrections: applied %d/%d fix(es)", applied, len(_FIXES))
    for key, correct in remaining.items():
        logger.warning(
            "colocados_corrections: fix for %s/%s/%s (wrong=%s, correct=%s) didn't "
            "match any row -- institution text may have shifted since this was written",
            key[0], key[2], key[3], key[1], correct,
        )
    return rows
