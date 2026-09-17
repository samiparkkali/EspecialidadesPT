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

import csv
import re
import unicodedata
from pathlib import Path

_OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "institution_overrides.csv"


def _load_overrides() -> dict[str, str]:
    """Hand-maintained corrections for near-duplicate canonical names that
    survive automatic normalization (OCR letter swaps, abbreviations like
    "IPO" vs. the spelled-out name, etc.) -- see
    `python backend/find_institution_clusters.py`, which generates/refreshes
    this file with suggested groupings for a human to fix by hand. Keyed by
    whatever `canonicalize()` would otherwise return, mapped to the name it
    should actually resolve to. Missing file / stray columns are fine: this
    is optional polish on top of the regex-based normalization above.
    """
    overrides: dict[str, str] = {}
    if not _OVERRIDES_PATH.exists():
        return overrides
    with open(_OVERRIDES_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = (row.get("canonical_institution") or "").strip()
            corrected = (row.get("corrected_name") or "").strip()
            if raw and corrected and raw != corrected:
                overrides[raw] = corrected
    return overrides


_OVERRIDES = _load_overrides()

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
        # "Centro Hospitalar Universitário do Porto" (CHUP) was this same
        # entity's name before its ~2019 rename to Santo António -- some
        # years' PDFs (and even some rows within a single-year PDF) still use
        # the older name.
        "Centro Hospitalar Universitário do Porto",
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
    # Not to be confused with the distinct "ACES de Lisboa Ocidental e
    # Oeiras" primary-care cluster, which never merged into this ULS -- the
    # patterns below are anchored to "Centro Hospitalar"/"ULS" so they can't
    # accidentally swallow the ACES entity via a bare "Lisboa Ocidental"
    # substring match.
    "ULS Lisboa Ocidental": [
        "Centro Hospitalar de Lisboa Ocidental",
        "ULS Lisboa Ocidental",
        "ULS de Lisboa Ocidental",
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
        # OCR misreads "Gaia" as "Gala" ("i" -> "l") on several pages.
        "Centro Hospitalar Vila Nova de Gala/Espinho",
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
        "ULS Almada-Seixal",
    ],
    "ULS Loures/Odivelas": [
        "Hospital Beatriz Ângelo",
        "Hospital de Loures",
        "ULS Loures/Odivelas",
        "ULS Loures-Odivelas",
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
    # Madeira's autonomous region never went through the mainland's 2023 ULS
    # reorg -- SESARAM ("Serviço de Saúde da Região Autónoma da Madeira") is
    # its own long-standing equivalent, and Hospital Nélio Mendonça is its
    # main hospital, administratively part of it.
    # Not a bare "SESARAM" pattern -- that would also swallow the distinct
    # "SESARAM - Unidade de Saúde Pública de <X>" clinic entries and the
    # "Sesaram (vaga protocolada - <other institution>)" cross-region
    # placement rows, both of which must stay separate.
    "SESARAM": [
        "Hospital Nélio Mendonça",
        "Hospital Dr. Nélio Mendonça",
    ],
    "ULS Guarda": [
        "ULS Guarda",
        "ULS da Guarda",
        # OCR misreads the leading "U" as "I" ("Inidade" for "Unidade") on
        # some pages -- _ULS_FULL_NAME's regex requires the real "Unidade"
        # spelling, so this typo needs its own pattern.
        "Inidade Local de Saúde da Guarda",
    ],
    # The following entries all come from Decreto-Lei n.º 102/2023's Art. 1,
    # which named every pre-2024 hospital/ACES pair merged into each new ULS
    # -- see EXTRACTION_FINDINGS.md. The general "ULS X"/"Unidade Local de
    # Saúde de/da/do X" pattern above (_ULS_FULL_NAME) already unifies both
    # spellings of the post-reorg name from a single "ULS X" pattern, so only
    # the pre-reorg hospital name needs listing here as well.
    "ULS Alto Ave": ["Hospital da Senhora da Oliveira", "ULS Alto Ave"],
    "ULS Barcelos/Esposende": [
        "Hospital de Santa Maria Maior",
        "ULS Barcelos/Esposende",
        "ULS Barcelos-Esposende",
    ],
    "ULS Póvoa de Varzim/Vila do Conde": [
        "Centro Hospitalar Póvoa de Varzim",
        "ULS Póvoa de Varzim/Vila do Conde",
        "ULS Póvoa de Varzim-Vila do Conde",
    ],
    "ULS Médio Ave": ["Centro Hospitalar do Médio Ave", "ULS Médio Ave"],
    "ULS Entre Douro e Vouga": [
        # Raw text spells this "Entre-Douro" (no "o") far more often than the
        # decree's official "Entre o Douro" -- the hyphen-insensitive
        # _match_key handles the hyphen/space variants, so both need listing.
        "Entre Douro e Vouga",
        "Entre o Douro e Vouga",
    ],
    "ULS Baixo Mondego": [
        "Hospital Distrital da Figueira da Foz",
        "ULS Baixo Mondego",
    ],
    "ULS Cova da Beira": [
        "Centro Hospitalar Universitário Cova da Beira",
        "Centro Hospitalar Cova da Beira",
        "ULS Cova da Beira",
    ],
    "ULS Viseu Dão-Lafões": [
        "Centro Hospitalar Tondela",
        "Centro Hospitalar Tondela-Viseu",
        "ULS Viseu Dão-Lafões",
        "ULS Dão-Lafões",
    ],
    "ULS Região de Leiria": [
        "Centro Hospitalar de Leiria",
        "ULS Região de Leiria",
        "ULS de Leiria",
    ],
    "ULS Região de Aveiro": [
        "Centro Hospitalar do Baixo Vouga",
        "ULS Região de Aveiro",
        "ULS de Aveiro",
    ],
    "ULS Amadora/Sintra": [
        "Hospital Professor Doutor Fernando Fonseca",
        "Hospital Fernando Fonseca",
        "ULS Amadora/Sintra",
        "ULS Amadora-Sintra",
    ],
    "ULS Lezíria": [
        "Hospital Distrital de Santarém",
        "ULS Lezíria",
    ],
    "ULS Estuário do Tejo": [
        "Hospital de Vila Franca de Xira",
        "ULS Estuário do Tejo",
    ],
    "ULS Oeste": ["Centro Hospitalar do Oeste", "ULS Oeste"],
    "ULS Médio Tejo": ["Centro Hospitalar do Médio Tejo", "ULS Médio Tejo"],
    "ULS Arrábida": ["Centro Hospitalar de Setúbal", "ULS Arrábida"],
    "ULS Arco Ribeirinho": [
        "Centro Hospitalar Barreiro",
        "Centro Hospitalar Barreiro-Montijo",
        "ULS Arco Ribeirinho",
    ],
    "ULS Alto Alentejo": [
        "ULS do Norte Alentejano",
        "ULS Norte Alentejano",
        "ULS Alto Alentejo",
    ],
    "ULS Alentejo Central": [
        # Not "Hospital Divino Espírito Santo de Ponta Delgada" -- a
        # different hospital in the Açores that never merged into this ULS.
        "Espírito Santo de Évora",
        "ULS Alentejo Central",
    ],
    # The 3 IPO ("Instituto Português de Oncologia ... Francisco Gentil")
    # sites appear under their full name, an abbreviated "IPO <city>" form,
    # and a long tail of OCR letter-swaps on "Instituto Português" itself
    # (e.g. "Lxstituto", "Ostituto") -- matching on "Oncologia de/do <city>
    # Francisco Gentil" (a substring OCR rarely corrupts, since it isn't at
    # a line's leading edge) plus the "IPO <city>" abbreviation catches
    # every variant without needing to enumerate each typo.
    "IPO Coimbra Francisco Gentil": [
        # Some years print a comma before "Francisco Gentil" ("Oncologia de
        # Coimbra, Francisco Gentil"), others don't -- both need matching.
        "Oncologia de Coimbra, Francisco Gentil",
        "Oncologia de Coimbra Francisco Gentil",
        "IPO Coimbra",
    ],
    "IPO Lisboa Francisco Gentil": [
        "Oncologia de Lisboa, Francisco Gentil",
        "Oncologia de Lisboa Francisco Gentil",
        "IPO Lisboa",
    ],
    "IPO Porto Francisco Gentil": [
        "Oncologia do Porto, Francisco Gentil",
        "Oncologia do Porto Francisco Gentil",
        "Oncologia do Parto Francisco Gentil",
        "IPO Porto",
    ],
}


# MGF (and a few other specialties) nest one level deeper than
# hospital/ULS -- down to the individual primary-care clinic (USF/UCSP/USP/
# UCC). The clinic itself survived the 2024 ACES->ULS reorganization
# unchanged; only its parent org's name changed (e.g. "ACES Arco Ribeirinho
# - USF Ribeirinha" -> "ULS Arco Ribeirinho - USF Ribeirinha"). Matching on
# the clinic name alone reconciles these across the reorg instead of losing
# their whole placement history at the rename.
_CLINIC_SUFFIX = re.compile(r"\b(USF|UCSP|USP|UCC)\s+.+$", re.IGNORECASE)
# 2022 colocados.csv has a font/cmap glitch (the same one that corrupts some
# ordering numbers -- see extract_colocados_native_full.py) that renders the
# "U" of "USF" as a stray digit (observed: 0SF, 3SF, 4SF, 5SF). Left
# unhandled, each corrupted row falls through to the raw-uppercase fallback
# as its own bogus one-off "institution" instead of reconciling with every
# correctly-spelled "USF <clinic>" elsewhere.
_CLINIC_SUFFIX_GLITCHED = re.compile(r"\b[0-9]SF\s+.+$", re.IGNORECASE)

# "E.P.E." (the standard "public entity" suffix on almost every hospital
# name) shows up with every spacing/punctuation/OCR variant imaginable
# across years -- ", E.P.E.", ", E. P. E", ", E.P.E," and the OCR glitch
# "EFE." (P misread as F) -- each treated as a distinct institution unless
# collapsed to one spelling before dedup/grouping.
_EPE_SUFFIX = re.compile(r",?\s*E\.?\s*P\.?\s*E\.?\s*[.,]?\s*$", re.IGNORECASE)
_EFE_SUFFIX = re.compile(r",?\s*EFE\.?\s*$", re.IGNORECASE)
# A compound place name's separating dash also varies by year/OCR pass:
# plain hyphen, en/em dash, or a stray "." used as a word separator
# ("TONDELA . VISEU" for "TONDELA - VISEU") -- normalize all of these to a
# single " - " so the same institution doesn't fork into several canonical
# entries over pure punctuation noise. The period form only ever separates
# two multi-letter words (never single-letter abbreviations like "E.P.E."),
# so requiring 2+ word characters on each side keeps those safe.
_DASH_VARIANTS = re.compile(r"\s*[‐-―]\s*")
_PERIOD_AS_DASH = re.compile(r"(?<=\w{2})\s*\.\s*(?=\w{2})")

# "ULS <X>" is just the abbreviation for "Unidade Local de Saúde de/da/do
# <X>" -- both spellings show up across years/PDFs for the same entity (e.g.
# "ULS Guarda, EPE" vs. "Unidade Local de Saúde da Guarda"). Collapsing the
# spelled-out form down to "ULS" means a single CANONICAL_MAP entry (or even
# no entry at all, for ULSs that never had a distinct pre-reorg name) covers
# both, instead of needing every ULS's full name enumerated as its own
# pattern.
_ULS_FULL_NAME = re.compile(r"Unidade\s+Local\s+de\s+Sa[uú]de\s*(?:de|da|do)?\s*", re.IGNORECASE)
# The connecting article ("de"/"da"/"do") between an institution's generic
# type and its place name drifts year to year in ways a reader never
# notices ("Centro Hospitalar Universitário de Lisboa Norte" vs "... Lisboa
# Norte") -- stripped only for matching purposes, never for the display name.
_ARTICLE = re.compile(r"\b(?:de|da|do)\b\s*", re.IGNORECASE)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _match_key(text: str) -> str:
    """Accent-insensitive, article-insensitive, ULS-form-insensitive,
    hyphen-insensitive key used only to decide whether a CANONICAL_MAP
    pattern matches a raw name -- never used as the displayed canonical name
    itself (compound names' real hyphens, e.g. "Trás-os-Montes", are
    unaffected since both sides of a comparison go through this same
    normalization)."""
    text = _strip_accents(text)
    text = _ULS_FULL_NAME.sub("ULS ", text)
    text = _ARTICLE.sub("", text)
    text = _DASH_VARIANTS.sub(" ", text)
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip().upper()


def _normalize_formatting(name: str) -> str:
    if _EFE_SUFFIX.search(name):
        name = _EFE_SUFFIX.sub(", E.P.E.", name)
    elif _EPE_SUFFIX.search(name):
        name = _EPE_SUFFIX.sub(", E.P.E.", name)
    name = _DASH_VARIANTS.sub(" - ", name)
    name = _PERIOD_AS_DASH.sub(" - ", name)
    name = _ULS_FULL_NAME.sub("ULS ", name)
    return re.sub(r"\s+", " ", name).strip()


def canonicalize(raw_institution: str) -> str:
    """Best-effort canonical name (display/filter form -- always uppercase,
    e.g. so a badly-cased "Aces Tamega Ii" reads as "... II" like the roman
    numeral it is, not title-cased into something misleading). Falls back to
    the raw name (uppercased) if no canonical mapping matches."""
    if not raw_institution:
        return raw_institution
    # Some years print "Gaia / Espinho", others "Gaia/Espinho" -- normalize
    # spacing around "/" before matching so a purely cosmetic difference
    # doesn't split one institution into two distinct canonical names.
    normalized = re.sub(r"\s*/\s*", "/", raw_institution)

    # A clinic (USF/UCSP/USP/UCC) suffix names the actual leaf institution --
    # check this BEFORE CANONICAL_MAP, otherwise a parent ULS/hospital that
    # happens to have its own CANONICAL_MAP entry (e.g. "ULS Matosinhos")
    # would swallow "ULS Matosinhos - USF Foo" into the parent's canonical
    # name, silently losing the clinic-level granularity that MGF depends on.
    if (clinic_match := _CLINIC_SUFFIX.search(normalized)) is not None:
        result = _normalize_formatting(clinic_match.group(0)).upper()
        return _OVERRIDES.get(result, result)
    if (glitched_match := _CLINIC_SUFFIX_GLITCHED.search(normalized)) is not None:
        result = _normalize_formatting("USF" + glitched_match.group(0)[3:]).upper()
        return _OVERRIDES.get(result, result)

    match_text = _match_key(normalized)
    for canonical, patterns in CANONICAL_MAP.items():
        for pattern in patterns:
            if _match_key(pattern) in match_text:
                return canonical.upper()

    result = _normalize_formatting(normalized).upper()
    return _OVERRIDES.get(result, result)


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
