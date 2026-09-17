"""Renders data/processed/vagas.csv and data/processed/colocados.csv into one
readable Markdown file per year per dataset under data/processed/markdown/,
grouped specialty > region > institution (vagas) or specialty > institution
(colocados), so every mapped seat/placement can be scanned/checked against
the raw extracted text in data/processed/extracted_text/ without opening a
spreadsheet.

Run after build_dataset.py: python backend/build_markdown.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAGAS_CSV = ROOT / "data" / "processed" / "vagas.csv"
COLOCADOS_CSV = ROOT / "data" / "processed" / "colocados.csv"
OUT_DIR = ROOT / "data" / "processed" / "markdown"


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(VAGAS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_year: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r)

    for year, year_rows in sorted(by_year.items()):
        by_specialty: dict[str, list[dict]] = defaultdict(list)
        for r in year_rows:
            by_specialty[r["specialty"]].append(r)

        lines = [f"# Vagas {year} -- seats by specialty / region / institution", ""]
        year_total = sum(int(r["seats"]) for r in year_rows)
        lines.append(f"**Total seats this year: {year_total}**")
        lines.append("")

        for specialty in sorted(by_specialty):
            spec_rows = by_specialty[specialty]
            spec_total = sum(int(r["seats"]) for r in spec_rows)
            lines.append(f"## {specialty} ({spec_total})")
            lines.append("")

            by_region: dict[str, list[dict]] = defaultdict(list)
            for r in spec_rows:
                by_region[r["region"] or "(no region breakdown)"].append(r)

            for region in sorted(by_region):
                region_rows = by_region[region]
                region_total = sum(int(r["seats"]) for r in region_rows)
                has_institution = any(r["institution"] for r in region_rows)

                if region == "(no region breakdown)" and not has_institution:
                    lines.append(f"- Total: {region_total}")
                    continue

                lines.append(f"### {region} ({region_total})")
                if has_institution:
                    lines.append("")
                    lines.append("| Institution | Seats |")
                    lines.append("|---|---|")
                    for r in sorted(region_rows, key=lambda r: r["institution"] or ""):
                        lines.append(f"| {r['institution']} | {r['seats']} |")
                lines.append("")

            lines.append("")

        out_path = OUT_DIR / f"vagas-{year}.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {out_path} ({len(by_specialty)} specialties, {year_total} seats)")

    build_colocados(rows)


def build_colocados(vagas_rows: list[dict]) -> None:
    with open(COLOCADOS_CSV, encoding="utf-8") as f:
        coloc_rows = list(csv.DictReader(f))

    # vagas.csv keeps only ONE granularity level per specialty (see
    # build_dataset.py's _leaf_rows_only) -- institution-level for most
    # specialties, region-level only for MGF -- so summing every row
    # regardless of whether `institution` is set never double-counts.
    vagas_seats: dict[tuple[str, str], int] = defaultdict(int)
    for r in vagas_rows:
        vagas_seats[(r["year"], r["specialty"])] += int(r["seats"])

    by_year: dict[str, list[dict]] = defaultdict(list)
    for r in coloc_rows:
        by_year[r["year"]].append(r)

    for year, year_rows in sorted(by_year.items()):
        by_specialty: dict[str, list[dict]] = defaultdict(list)
        for r in year_rows:
            by_specialty[r["specialty"]].append(r)

        lines = [f"# Colocados {year} -- placements by specialty / institution", ""]
        lines.append(f"**Total placements this year: {len(year_rows)}**")
        lines.append("")

        for specialty in sorted(by_specialty):
            spec_rows = by_specialty[specialty]
            seats = vagas_seats.get((year, specialty))
            seats_note = f" -- seats offered: {seats}" if seats is not None else " -- not offered this year"
            lines.append(f"## {specialty} ({len(spec_rows)} placed{seats_note})")
            lines.append("")

            by_institution: dict[str, int] = defaultdict(int)
            for r in spec_rows:
                by_institution[r["canonical_institution"] or r["institution"] or "(unknown)"] += 1

            lines.append("| Institution | Placements |")
            lines.append("|---|---|")
            for inst in sorted(by_institution):
                lines.append(f"| {inst} | {by_institution[inst]} |")
            lines.append("")

        out_path = OUT_DIR / f"colocados-{year}.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {out_path} ({len(by_specialty)} specialties, {len(year_rows)} placements)")


if __name__ == "__main__":
    build()
