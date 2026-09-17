"""Groups canonical_institution values that likely refer to the same real
institution but differ due to spacing/punctuation/OCR noise (E.P.E. vs
E. P. E. vs EFE., hyphen vs en-dash, a stray period used as a word
separator, single-letter OCR swaps), and writes them to a hand-editable CSV.

Clustering key: strip accents, collapse E.P.E./EFE./E. P. E. variants,
replace all dash-like/period-as-separator punctuation with a single space,
then compare. Only names that collapse to the EXACT same key are grouped --
deliberately conservative (no transitive fuzzy chaining) so it doesn't drag
unrelated institutions into the same cluster the way a loose word-overlap
match would.

Usage:
    python backend/find_institution_clusters.py
    -> writes data/institution_overrides.csv, one row per canonical name
       that shares a cluster with at least one other spelling, with a
       `corrected_name` column pre-filled with the cluster's most common
       spelling. Edit that column by hand for any row where the guess is
       wrong (e.g. an OCR letter-swap cluster like "GAIA" vs "GALA" --
       these share a key only if the swap doesn't change the significant
       letters, so check each cluster's members before trusting the
       pre-fill). Then re-run backend/build_dataset.py to apply it (see
       institution_mapping.py's `_load_overrides`).
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OVERRIDES_PATH = ROOT / "data" / "institution_overrides.csv"

_EPE_SUFFIX = re.compile(r",?\s*E\.?\s*[.,]?\s*P\.?\s*[.,]?\s*E\.?\s*[.,]?\s*$", re.IGNORECASE)
_EFE_SUFFIX = re.compile(r",?\s*EFE\.?\s*$", re.IGNORECASE)
_PUNCT_AS_SEPARATOR = re.compile(r"[\s\-‐-―./,]+")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _cluster_key(name: str) -> str:
    name = _strip_accents(name).upper()
    if _EFE_SUFFIX.search(name):
        name = _EFE_SUFFIX.sub(" EPE", name)
    elif _EPE_SUFFIX.search(name):
        name = _EPE_SUFFIX.sub(" EPE", name)
    return _PUNCT_AS_SEPARATOR.sub(" ", name).strip()


def _load_counts() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for name in ("vagas.csv", "colocados.csv"):
        path = PROCESSED / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                inst = row.get("canonical_institution", "")
                if inst:
                    counts[inst] += 1
    return counts


def main() -> None:
    counts = _load_counts()
    by_key: dict[str, list[str]] = defaultdict(list)
    for name in counts:
        by_key[_cluster_key(name)].append(name)
    clusters = {k: v for k, v in by_key.items() if len(v) > 1}

    rows = []
    for cluster_id, (_key, members) in enumerate(
        sorted(clusters.items(), key=lambda kv: -sum(counts[m] for m in kv[1]))
    ):
        suggested = max(members, key=lambda m: counts[m])
        for m in sorted(members, key=lambda m: -counts[m]):
            rows.append(
                {"cluster": cluster_id, "canonical_institution": m, "count": counts[m], "corrected_name": suggested}
            )

    with open(OVERRIDES_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["cluster", "canonical_institution", "count", "corrected_name"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {OVERRIDES_PATH} -- {len(clusters)} clusters, {len(rows)} rows")
    print("review/edit the `corrected_name` column by hand, then re-run backend/build_dataset.py")


if __name__ == "__main__":
    main()
