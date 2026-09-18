"""Maps raw institution names to a canonical identity for cross-year analysis.

Portugal's 2024/2025 SNS reorg merged separate hospital + ACES entities into
single "ULS <region>" entities; without this mapping the same hospital looks
like a new institution in 2025, breaking cross-year trends.

Best-effort table from names observed in data/processed/vagas.csv, not
exhaustive. Run `python backend/institution_mapping.py data/processed/vagas.csv`
to list unmapped names and extend CANONICAL_MAP as needed.

Raw name is always kept alongside canonical in processed data (never
overwritten); see CLAUDE.md's "keep source columns" guidance.
"""

from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from pathlib import Path

_OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "institution_overrides.csv"


def _load_overrides() -> dict[str, str]:
    """Hand-maintained corrections for near-duplicates that survive automatic
    normalization; see `find_institution_clusters.py`, which generates this
    file's suggested groupings. Keyed by canonicalize()'s output, mapped to
    the name it should resolve to. Missing file is fine (optional polish)."""
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
    # Azores: some years use the formal name, others the island name -- same location.
    "Hospital da Horta": [
        "Hospital da Horta",
        "Hospital da Horta - Ilha do Faial",
    ],
    "Hospital de Santo Espírito de Angra do Heroísmo": [
        "Hospital de Santo Espirito de Angra do Heroismo",
        "Hospital de Santo Espirito da Ilha Terceira",
        "Hospital Santo Espirito Ilha Terceira",
    ],
    "ULS Litoral Alentejano": [
        "ULS Litoral Alentejano",
        "ULS do Litoral Alentejano",
    ],
    # These 4 already are their post-reform canonical form, but ", E.P.E."
    # suffix presence varies by row and isn't stripped by the generic
    # formatting -- needs an entry or they'd split into two canonical names.
    "ULS Castelo Branco": ["ULS Castelo Branco"],
    "ULS Alto Minho": ["ULS Alto Minho"],
    "ULS Baixo Alentejo": ["ULS Baixo Alentejo"],
    "ULS Nordeste": ["ULS Nordeste"],
    # Some years drop "do" entirely -- would otherwise split into two names.
    "Hospital Divino Espírito Santo de Ponta Delgada": [
        "Hospital Divino Espírito Santo de Ponta Delgada",
        "Hospital do Divino Espírito Santo de Ponta Delgada",
    ],
    "ULS São João": [
        "Centro Hospitalar Universitário de São João",
        "ULS São João",
        "ULS de São João",
    ],
    "ULS Santo António": [
        "Centro Hospitalar Universitário de Santo António",
        # Pre-~2019 name for this same entity (CHUP), still used in some PDFs.
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
    # Anchored to "Centro Hospitalar"/"ULS" so a bare "Lisboa Ocidental"
    # substring can't swallow the distinct, never-merged "ACES de Lisboa
    # Ocidental e Oeiras" primary-care cluster.
    "ULS Lisboa Ocidental": [
        "Centro Hospitalar de Lisboa Ocidental",
        "ULS Lisboa Ocidental",
        "ULS de Lisboa Ocidental",
    ],
    "ULS Coimbra": [
        "Centro Hospitalar e Universitário de Coimbra",
        "ULS Coimbra",
        "ULS de Coimbra",
        # Its rehab-medicine site, printed under a completely unrelated full
        # name in colocados ("Centro Medicina de Reabilitação da Região
        # Centro Rovisco Pais") that shares no substring with "Coimbra".
        "Rovisco Pais",
    ],
    "ULS Braga": [
        "Hospital de Braga",
        "ULS Braga",
        "ULS de Braga",
    ],
    "ULS Gaia/Espinho": [
        "Centro Hospitalar Vila Nova de Gaia/Espinho",
        # OCR "i" -> "l" typo: "Gala" for "Gaia".
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
    # Madeira never went through the mainland's ULS reorg; SESARAM is the
    # whole regional service (kept unmapped), not this specific hospital, so
    # it's excluded here (handled separately below as an exact match) to
    # avoid swallowing the distinct SESARAM clinic/cross-region-placement rows.
    # "Nélio Mendonça"/"Dr. Nélio Mendonça" is this hospital's older name.
    "Hospital Central do Funchal": [
        "Hospital Central do Funchal",
        "Hospital Central do Fxnchal",
        "Hospital Cefitral do Funchal",
        "lospital Central do Funchal",
        "Hospital Nélio Mendonça",
        "Hospital Dr. Nélio Mendonça",
    ],
    "ULS Guarda": [
        "ULS Guarda",
        "ULS da Guarda",
        # OCR "U"->"I" typo ("Inidade"); _ULS_FULL_NAME only matches real "Unidade".
        "Inidade Local de Saúde da Guarda",
    ],
    # Pre-2024 hospital/ACES pairs per Decreto-Lei n.º 102/2023 Art. 1 (see
    # EXTRACTION_FINDINGS.md); only the pre-reorg name needs listing since
    # _ULS_FULL_NAME already unifies both post-reorg spellings.
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
        # "Entre Douro" (common) vs. the decree's official "Entre o Douro".
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
        # Dominant raw spelling abbreviates "Professor Doutor" to "Prof Dr".
        "Hospital Prof Dr Fernando Fonseca",
        "Hospital Fernando Fonseca",
        # Catches OCR-garbled title prefixes ("Frof", "Or") that break the
        # word-contiguity the patterns above need to match.
        "Fernando Fonseca",
        "Fernaodo Fonseca",
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
    # Private hospital in Vila Nova de Gaia (Norte), rebranded under Luz
    # Saúde -- distinct from the public "ULS Arrábida" (Setúbal) above, and
    # from the flagship "Hospital da Luz" (Lisboa) below. Listed first so
    # its more specific "Arrábida" suffix wins before the bare-name entry's
    # substring check could otherwise swallow it.
    "Hospital da Luz Arrábida": ["Hospital da Arrábida", "Hospital da Luz Arrábida"],
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
        # Distinct from "Hospital Divino Espírito Santo de Ponta Delgada" (Açores).
        "Espírito Santo de Évora",
        "ULS Alentejo Central",
    ],
    # Matching "Oncologia de/do <city> Francisco Gentil" + "IPO <city>" covers
    # every OCR typo variant of "Instituto Português" without enumerating them.
    "IPO Coimbra": [
        # Comma before "Francisco Gentil" varies by year -- both needed.
        "Oncologia de Coimbra, Francisco Gentil",
        "Oncologia de Coimbra Francisco Gentil",
        "IPO Coimbra",
    ],
    "IPO Lisboa": [
        "Oncologia de Lisboa, Francisco Gentil",
        "Oncologia de Lisboa Francisco Gentil",
        "IPO Lisboa",
    ],
    "IPO Porto": [
        "Oncologia do Porto, Francisco Gentil",
        "Oncologia do Porto Francisco Gentil",
        "Oncologia do Parto Francisco Gentil",
        "IPO Porto",
    ],
    # Private CUF hospitals: rows drop "Hospital" or reorder to "CUF X Hospital".
    "Hospital CUF Descobertas": [
        "CUF Descobertas",
    ],
    "Hospital CUF Porto": [
        "CUF Porto",
    ],
    "Hospital CUF Tejo": [
        # Absorbed the older "CUF Infante Santo" site/name.
        "CUF Infante Santo",
        "CUF Tejo",
    ],
    # Only the Lisboa site appears in this dataset, so unifying on the bare
    # group name is safe (no risk of merging distinct Lusíadas hospitals).
    "Hospital Lusíadas": [
        "Hospital dos Lusíadas",
        "Hospital Lusíadas Lisboa",
        "Hospital Lusíadas",
    ],
    "Hospital de Cascais Dr. José de Almeida": [
        "Hospital de Cascais Dr",
        "HPP Hospital de Cascais",
        "LPP Hospital de Cascais",  # OCR "L" for "H"
        "Hospital Público Privado de Cascais",
        "Hospital Público-Privado de Cascais",
    ],
    # Flagship Lisboa site; most years print it bare, 2024 adds "Lisboa".
    # Character-similar enough to "Hospital Lusíadas" (same padding words,
    # short overall length) that the fuzzy fallback below would otherwise
    # misfire on it -- needs an explicit substring pattern instead.
    "Hospital da Luz": ["Hospital da Luz Lisboa", "Hosp. da Luz", "Hospital da Luz"],
    # Instituto Nacional de Medicina Legal e Ciências Forenses -- its 3
    # regional delegations print under at least 4 different naming
    # conventions across years ("Instituto Nacional Medicina Legal", the
    # newer "Instituto Nacional de Medicina Legal", the acronym "INMLCF",
    # or a bare "Delegação do X" with the parent org dropped entirely), on
    # top of which OCR frequently corrupts "Delegação"'s accented letters --
    # never unified before, so each variant silently became its own
    # institution instead of accumulating the delegation's placements.
    # Centro's Aveiro sub-office listed first: it's a genuinely separate
    # office from the bare "Delegação do Centro", so needs to claim its
    # more specific pattern before the generic one below can swallow it.
    "INML Delegação do Centro (Aveiro)": [
        "Instituto Nacional Medicina Legal - Delegação do Centro (Aveiro)",
        "Delegação do Centro (Aveiro)",
    ],
    "INML Delegação do Norte": [
        "Instituto Nacional Medicina Legal - Delegação do Norte",
        "Instituto Nacional de Medicina Legal - Delegação Norte",
        "INMLCF Delegação Norte",
        "Delegação do Norte",
        "Delegação Norte",
    ],
    "INML Delegação do Centro": [
        "Instituto Nacional Medicina Legal - Delegação do Centro",
        "Instituto Nacional de Medicina Legal - Delegação Centro",
        "INMLCF Delegação Centro",
        "Delegação do Centro",
    ],
    # Portugal's INMLCF headquarters this delegation in Lisboa, so "Delegação
    # Lisboa" (INMLCF's own acronym-era naming) and "Delegação do Sul" (the
    # official delegation name) are the same office, not two.
    "INML Delegação do Sul": [
        "Instituto Nacional Medicina Legal - Delegação do Sul",
        "INMLCF Delegação Lisboa",
        "Delegação do Sul",
        "Delegação Lisboa",
    ],
}


# MGF etc. nest down to the individual clinic (USF/UCSP/USP/UCC), which
# survived the 2024 ACES->ULS reorg unchanged even though its parent org's
# name changed -- matching on the clinic name alone reconciles across that.
_CLINIC_SUFFIX = re.compile(r"\b(USF|UCSP|USP|UCC)\s+.+$", re.IGNORECASE)
# 2022 colocados.csv font/cmap glitch renders "USF"'s leading "U" as a stray
# digit (0SF, 3SF, 4SF, 5SF) -- see extract_colocados_native_full.py.
_CLINIC_SUFFIX_GLITCHED = re.compile(r"\b[0-9]SF\s+.+$", re.IGNORECASE)

# ", E.P.E." varies in spacing/punctuation across years, plus the OCR glitch
# "EFE." (P misread as F).
_EPE_SUFFIX = re.compile(r",?\s*E\.?\s*P\.?\s*E\.?\s*[.,]?\s*$", re.IGNORECASE)
_EFE_SUFFIX = re.compile(r",?\s*E\.?\s*F\.?\s*E\.?\s*[.,]?\s*$", re.IGNORECASE)
# Compound place-name dash varies: hyphen, en/em dash, or a stray "." used as
# a word separator ("TONDELA . VISEU"). Period form requires 2+ word chars on
# each side so it never matches single-letter abbreviations like "E.P.E.".
_DASH_VARIANTS = re.compile(r"\s*[‐-―]\s*")
_PERIOD_AS_DASH = re.compile(r"(?<=\w{2})\s*\.\s*(?=\w{2})")

# Collapses "Unidade Local de Saúde de/da/do <X>" to "ULS <X>" so both
# spellings match a single CANONICAL_MAP pattern.
_ULS_FULL_NAME = re.compile(r"Unidade\s+Local\s+de\s+Sa[uú]de\s*(?:de|da|do)?\s*", re.IGNORECASE)
# Connecting article ("de"/"da"/"do") drifts year to year -- stripped for
# matching only, never for the display name.
_ARTICLE = re.compile(r"\b(?:de|da|do)\b\s*", re.IGNORECASE)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _match_key(text: str) -> str:
    """Normalization key for matching only, never used as the display name
    (real hyphens like "Trás-os-Montes" are unaffected since both sides of a
    comparison go through the same normalization)."""
    text = _strip_accents(text)
    # Strip before the period-stripping below turns ", E.P.E." into a
    # trailing "E P E" that no longer matches either suffix regex -- without
    # this, "SESARAM" and "SESARAM, E.P.E." produce different keys and the
    # exact-match special case for bare "SESARAM" (see below) never fires
    # for rows that print the full corporate suffix.
    text = _EFE_SUFFIX.sub("", text)
    text = _EPE_SUFFIX.sub("", text)
    text = _ULS_FULL_NAME.sub("ULS ", text)
    text = _ARTICLE.sub("", text)
    text = _DASH_VARIANTS.sub(" ", text)
    text = text.replace("-", " ")
    # "Prof./Dr." vs "Prof - Dr -" must reduce to the same key.
    text = text.replace(".", " ")
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

    # Checked before CANONICAL_MAP so a parent ULS/hospital entry (e.g. "ULS
    # Matosinhos") doesn't swallow "ULS Matosinhos - USF Foo" and lose the
    # clinic-level granularity MGF depends on.
    if (clinic_match := _CLINIC_SUFFIX.search(normalized)) is not None:
        # Strip trailing "]" from rows like "... [USP Cascais]" (greedy match).
        clinic_name = clinic_match.group(0).rstrip("]").rstrip()
        result = _normalize_formatting(clinic_name).upper()
        return _OVERRIDES.get(result, result)
    if (glitched_match := _CLINIC_SUFFIX_GLITCHED.search(normalized)) is not None:
        result = _normalize_formatting("USF" + glitched_match.group(0)[3:]).upper()
        return _OVERRIDES.get(result, result)

    match_text = _match_key(normalized)

    # Bare "SESARAM" names the hospital seat itself; exact match only, since
    # "SESARAM - Unidade de Saúde Pública de X" and "Sesaram (vaga
    # Protocolada - X)" are genuinely different entities.
    if match_text == "SESARAM":
        return _OVERRIDES.get("HOSPITAL CENTRAL DO FUNCHAL", "HOSPITAL CENTRAL DO FUNCHAL")

    # 2025 colocados OCR truncated these to just the tail after the dash --
    # exact match only, so it can't sweep in "USF São Vicente" (a real, different clinic).
    if match_text == "SAO VICENTE":
        result = "SESARAM - UNIDADE DE SAÚDE PÚBLICA DE SÃO VICENTE"
        return _OVERRIDES.get(result, result)
    if match_text == "FUNCHAL":
        result = "SESARAM - UNIDADE DE SAÚDE PÚBLICA DO FUNCHAL"
        return _OVERRIDES.get(result, result)

    for canonical, patterns in CANONICAL_MAP.items():
        for pattern in patterns:
            if _match_key(pattern) in match_text:
                return _OVERRIDES.get(canonical.upper(), canonical.upper())

    # Substring matching above requires an intact contiguous run of the
    # pattern text, which some colocados PDFs' character-level OCR noise
    # destroys (e.g. "Centro Hospitalar Universitário de São 2030, E.P.E."
    # for São João) -- these rows were silently orphaned into their own
    # one-off "canonical" name instead of merging with the real hospital,
    # which understated that hospital's placement count. A same-length
    # fuzzy match against every CANONICAL_MAP pattern recovers most of
    # these; 0.80 and a 15-char floor were picked by checking every match
    # produced against the real orphan names in colocados.csv (see
    # `python find_institution_clusters.py`-style audit in EXTRACTION_FINDINGS.md)
    # -- below that, short/generic fragments ("HOSPITAL" alone, "PENA")
    # start fuzzy-matching to the wrong hospital.
    #
    # Ratio alone isn't enough: "Hospital da Luz" (a real, distinct hospital
    # with no CANONICAL_MAP entry of its own) scores 0.84 against "Hospital
    # Lusíadas" purely from sharing "HOSPITAL"/"LISBOA" padding around a
    # completely different name -- a false merge, not OCR noise. OCR
    # corruption instead leaves one long contiguous run of the original
    # name intact (only a middle chunk garbled), so also requiring the
    # longest common substring to cover most of the pattern's length
    # rejects same-shape-different-name collisions like that one while
    # still passing every verified true positive (>=0.66 there vs 0.46
    # for the Luz/Lusíadas collision).
    if len(match_text) >= 15:
        best_canonical, best_ratio, best_block_frac = None, 0.0, 0.0
        for canonical, patterns in CANONICAL_MAP.items():
            for pattern in patterns:
                pattern_key = _match_key(pattern)
                sm = difflib.SequenceMatcher(None, match_text, pattern_key)
                ratio = sm.ratio()
                if ratio > best_ratio:
                    block = sm.find_longest_match(0, len(match_text), 0, len(pattern_key))
                    best_canonical, best_ratio = canonical, ratio
                    best_block_frac = block.size / len(pattern_key) if pattern_key else 0
        if best_ratio >= 0.80 and best_block_frac >= 0.60:
            return _OVERRIDES.get(best_canonical.upper(), best_canonical.upper())

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
