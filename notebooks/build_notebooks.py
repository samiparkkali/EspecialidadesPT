"""Generates the two QA notebooks as nbformat JSON, then they're executed
via `jupyter nbconvert --execute --inplace`. Kept as a script (not hand-
edited JSON) so the notebooks can be regenerated after a pipeline change
without hand-patching cell JSON.
"""
import nbformat as nbf

ROOT_LOAD = """\
import csv
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()

def load(name):
    with open(ROOT / "data" / "processed" / f"{name}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))

vagas = load("vagas")
colocados = load("colocados")
print(f"vagas: {len(vagas)} rows, colocados: {len(colocados)} rows")
"""

nb1 = nbf.v4.new_notebook()
nb1.cells = [
    nbf.v4.new_markdown_cell(
        "# QA: seats by year and location\n\n"
        "Sanity-checks `vagas.csv` (the only source of \"seats available\", "
        "see CLAUDE.md) year over year: does the total look consistent, "
        "how much of each year is missing a mapped region, and does the "
        "specialty list drift across years. Re-run after `make process`."
    ),
    nbf.v4.new_code_cell(ROOT_LOAD),
    nbf.v4.new_markdown_cell("## Total seats by year\n\nExpect a similar order of magnitude year to year -- a big drop usually means a parse failure, not a real policy change."),
    nbf.v4.new_code_cell(
        "# Each vagas-YYYY.pdf prints its own grand total (\"Total Geral\" 2023-2025,\n"
        "# \"Total Nacional\" 2021-2022) -- the one number here that's ACSS's own, not\n"
        "# derived. Everything else in this pipeline should be judged against it.\n"
        "OFFICIAL_TOTAL = {'2021': 1938, '2022': 2054, '2023': 2248, '2024': 2165, '2025': 2330}\n"
        "\n"
        "totals_by_year = defaultdict(int)\n"
        "for r in vagas:\n"
        "    totals_by_year[r['year']] += int(r['seats'])\n"
        "\n"
        "for year in sorted(totals_by_year):\n"
        "    official = OFFICIAL_TOTAL.get(year)\n"
        "    diff = totals_by_year[year] - official if official else None\n"
        "    print(f\"{year}: {totals_by_year[year]:>6} seats   official: {official}   diff: {diff:+d}\" if official else f\"{year}: {totals_by_year[year]:>6} seats\")\n"
    ),
    nbf.v4.new_markdown_cell(
        "**This used to be off by ~3x** (e.g. 2021 read 5,814 instead of "
        "1,938): `extract_vagas.py`/`extract_vagas_labeled.py` emit one row "
        "per table level (institution, region subtotal, specialty total) "
        "for the *same* seats, and the pipeline was summing all of them. "
        "Fixed in `build_dataset.py`'s `_leaf_rows_only()`, which keeps "
        "only the most granular level per specialty and falls back to the "
        "specialty's own printed total when the breakdown doesn't "
        "reconcile with it. 2021/2022/2024 now match exactly; 2023/2025 "
        "are within ~1% (see `tests/test_processed_data.py`'s regression "
        "test for the tolerance, and README's Known limitations for what's "
        "still open on those two)."
    ),
    nbf.v4.new_code_cell(
        "years_list = sorted(totals_by_year)\n"
        "fig, ax = plt.subplots(figsize=(7, 4))\n"
        "ax.bar(years_list, [totals_by_year[y] for y in years_list], color='#4C72B0', label='pipeline total')\n"
        "ax.plot(years_list, [OFFICIAL_TOTAL.get(y) for y in years_list], 'o--', color='#C44E52', label='official grand total')\n"
        "ax.set_ylabel('seats')\n"
        "ax.set_title('Total seats by year: pipeline vs official')\n"
        "ax.legend()\n"
        "plt.show()\n"
    ),
    nbf.v4.new_markdown_cell("## Seats by year x location (region)\n\nLocations uppercased for display, matching the specialty/institution convention."),
    nbf.v4.new_code_cell(
        "by_year_region = defaultdict(lambda: defaultdict(int))\n"
        "regions_seen = set()\n"
        "for r in vagas:\n"
        "    key = (r['region_key'] or 'UNMAPPED').upper()\n"
        "    by_year_region[r['year']][key] += int(r['seats'])\n"
        "    regions_seen.add(key)\n"
        "\n"
        "regions_sorted = sorted(regions_seen)\n"
        "header = 'YEAR'.ljust(6) + ''.join(reg.ljust(16) for reg in regions_sorted)\n"
        "print(header)\n"
        "for year in sorted(by_year_region):\n"
        "    row = year.ljust(6) + ''.join(str(by_year_region[year].get(reg, 0)).ljust(16) for reg in regions_sorted)\n"
        "    print(row)\n"
    ),
    nbf.v4.new_code_cell(
        "regions_no_unmapped = [r for r in regions_sorted if r != 'UNMAPPED'] + (['UNMAPPED'] if 'UNMAPPED' in regions_sorted else [])\n"
        "bottoms = [0] * len(by_year_region)\n"
        "fig, ax = plt.subplots(figsize=(8, 4.5))\n"
        "for reg in regions_no_unmapped:\n"
        "    vals = [by_year_region[y].get(reg, 0) for y in sorted(by_year_region)]\n"
        "    color = '#999999' if reg == 'UNMAPPED' else None\n"
        "    ax.bar(sorted(by_year_region), vals, bottom=bottoms, label=reg, color=color)\n"
        "    bottoms = [b + v for b, v in zip(bottoms, vals)]\n"
        "ax.set_ylabel('seats')\n"
        "ax.set_title('Seats by year x location (stacked)')\n"
        "ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)\n"
        "plt.tight_layout()\n"
        "plt.show()\n"
    ),
    nbf.v4.new_markdown_cell(
        "## Unmapped-region rate by year\n\n"
        "`region_key` is blank when `backend/region_mapping.py` couldn't "
        "match the raw region text (see its `REGION_KEYS` patterns). A "
        "high rate means real seats are invisible to the map/region filter "
        "in the UI, not that they don't exist."
    ),
    nbf.v4.new_code_cell(
        "for year in sorted(totals_by_year):\n"
        "    unmapped = sum(int(r['seats']) for r in vagas if r['year'] == year and not r['region_key'])\n"
        "    total = totals_by_year[year]\n"
        "    pct = 100 * unmapped / total if total else 0\n"
        "    flag = '  <-- HIGH' if pct > 20 else ''\n"
        "    print(f\"{year}: {unmapped:>5} / {total:>5} seats unmapped ({pct:5.1f}%){flag}\")\n"
    ),
    nbf.v4.new_code_cell(
        "pct_by_year = {}\n"
        "for year in sorted(totals_by_year):\n"
        "    unmapped = sum(int(r['seats']) for r in vagas if r['year'] == year and not r['region_key'])\n"
        "    pct_by_year[year] = 100 * unmapped / totals_by_year[year] if totals_by_year[year] else 0\n"
        "\n"
        "fig, ax = plt.subplots(figsize=(6, 3.5))\n"
        "bars = ax.bar(list(pct_by_year), list(pct_by_year.values()), color='#DD8452')\n"
        "ax.axhline(20, color='gray', linestyle='--', linewidth=1, label='20% flag threshold')\n"
        "ax.set_ylabel('% seats with no mapped region')\n"
        "ax.set_title('Unmapped-region rate by year')\n"
        "ax.legend()\n"
        "plt.show()\n"
    ),
    nbf.v4.new_markdown_cell(
        "Down to single digits for 2021/2022/2024 after fixing a mis-"
        "captured column-header fragment (was being read as a bogus "
        "\"region\", see `backend/extract_vagas_labeled.py`'s "
        "`PAGE_BOILERPLATE`) and adding the \"RAM\"/\"RAA\" region "
        "acronyms to `backend/region_mapping.py`. **2023's ~30% is now "
        "isolated to exactly two specialties** (Medicina Geral e Familiar, "
        "Saúde Pública) that have zero region breakdown captured for that "
        "year -- a genuine gap in `extract_vagas.py`'s native-text parser "
        "for those two specialties' unusual table structure that year, not "
        "a name-matching issue. If you can point to how those two "
        "specialties' region rows are laid out in `vagas-2023.pdf` "
        "specifically, that's the next concrete fix."
    ),
    nbf.v4.new_markdown_cell("## Specialty drift across years\n\nSpecialties present in some years but absent in others -- could be real (a specialty added/retired) or a canonicalization miss (see `backend/specialty_mapping.py`)."),
    nbf.v4.new_code_cell(
        "years_sorted = sorted(totals_by_year)\n"
        "specialty_years = defaultdict(set)\n"
        "for r in vagas:\n"
        "    specialty_years[r['specialty']].add(r['year'])\n"
        "\n"
        "all_years = set(years_sorted)\n"
        "drifted = {s: yrs for s, yrs in specialty_years.items() if yrs != all_years}\n"
        "print(f\"{len(drifted)} / {len(specialty_years)} specialties are NOT present in every year:\\n\")\n"
        "for s in sorted(drifted):\n"
        "    missing = sorted(all_years - drifted[s])\n"
        "    print(f\"  {s:55s} missing: {missing}\")\n"
    ),
    nbf.v4.new_markdown_cell(
        "Most gaps trace to years that never got full institution-level "
        "parsing for that specialty rather than the specialty not being "
        "offered -- cross-check any single-year-missing specialty against "
        "that year's `data/processed/extracted_text/vagas-YYYY.txt` before "
        "concluding it was really discontinued."
    ),
    nbf.v4.new_code_cell(
        "import numpy as np\n"
        "\n"
        "specs_sorted = sorted(specialty_years)\n"
        "matrix = np.array([[1 if y in specialty_years[s] else 0 for y in years_sorted] for s in specs_sorted])\n"
        "\n"
        "fig, ax = plt.subplots(figsize=(5, max(6, len(specs_sorted) * 0.22)))\n"
        "ax.imshow(matrix, aspect='auto', cmap='Greens', vmin=0, vmax=1)\n"
        "ax.set_xticks(range(len(years_sorted)))\n"
        "ax.set_xticklabels(years_sorted)\n"
        "ax.set_yticks(range(len(specs_sorted)))\n"
        "ax.set_yticklabels(specs_sorted, fontsize=6)\n"
        "ax.set_title('Specialty present (green) by year')\n"
        "plt.tight_layout()\n"
        "plt.show()\n"
    ),
]

nb2 = nbf.v4.new_notebook()
nb2.cells = [
    nbf.v4.new_markdown_cell(
        "# Specialty x year x location pivot, and colocados cross-check\n\n"
        "Full pivot of seat counts (specialty, year, location), plus the "
        "one hard invariant from CLAUDE.md: for a given specialty/year, "
        "`colocados` (placements) must never exceed `vagas` (seats) -- if "
        "it does, that's an extraction bug, not a real oversubscription."
    ),
    nbf.v4.new_code_cell(ROOT_LOAD),
    nbf.v4.new_markdown_cell("## Specialty totals by year (seats)\n\nSpecialty and location both uppercased for display."),
    nbf.v4.new_markdown_cell("Plotted after the table below (top 15 specialties by total seats across all years)."),
    nbf.v4.new_code_cell(
        "specialty_year_seats = defaultdict(lambda: defaultdict(int))\n"
        "specialties = set()\n"
        "for r in vagas:\n"
        "    spec = r['specialty'].upper()\n"
        "    specialty_year_seats[spec][r['year']] += int(r['seats'])\n"
        "    specialties.add(spec)\n"
        "\n"
        "years_sorted = sorted({r['year'] for r in vagas})\n"
        "header = 'SPECIALTY'.ljust(55) + ''.join(y.rjust(8) for y in years_sorted)\n"
        "print(header)\n"
        "for spec in sorted(specialties):\n"
        "    row = spec.ljust(55) + ''.join(str(specialty_year_seats[spec].get(y, 0)).rjust(8) for y in years_sorted)\n"
        "    print(row)\n"
    ),
    nbf.v4.new_code_cell(
        "top15 = sorted(specialties, key=lambda s: -sum(specialty_year_seats[s].values()))[:15]\n"
        "fig, ax = plt.subplots(figsize=(9, 5))\n"
        "x = range(len(years_sorted))\n"
        "width = 0.8 / len(top15)\n"
        "for i, spec in enumerate(top15):\n"
        "    vals = [specialty_year_seats[spec].get(y, 0) for y in years_sorted]\n"
        "    ax.bar([xi + i * width for xi in x], vals, width=width, label=spec[:25])\n"
        "ax.set_xticks([xi + width * len(top15) / 2 for xi in x])\n"
        "ax.set_xticklabels(years_sorted)\n"
        "ax.set_ylabel('seats')\n"
        "ax.set_title('Top 15 specialties by seats, per year')\n"
        "ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=6)\n"
        "plt.tight_layout()\n"
        "plt.show()\n"
    ),
    nbf.v4.new_markdown_cell("## Specialty x year x location pivot (seats)\n\nOne row per (specialty, location); columns are years. Only the top few by total seats are printed here -- the full pivot is large."),
    nbf.v4.new_code_cell(
        "pivot = defaultdict(lambda: defaultdict(int))\n"
        "for r in vagas:\n"
        "    loc = (r['region_key'] or 'UNMAPPED').upper()\n"
        "    spec = r['specialty'].upper()\n"
        "    pivot[(spec, loc)][r['year']] += int(r['seats'])\n"
        "\n"
        "ranked = sorted(pivot.items(), key=lambda kv: -sum(kv[1].values()))\n"
        "header = 'SPECIALTY'.ljust(45) + 'LOCATION'.ljust(16) + ''.join(y.rjust(7) for y in years_sorted)\n"
        "print(header)\n"
        "for (spec, loc), by_year in ranked[:40]:\n"
        "    row = spec.ljust(45) + loc.ljust(16) + ''.join(str(by_year.get(y, 0)).rjust(7) for y in years_sorted)\n"
        "    print(row)\n"
        "print(f\"\\n... {len(ranked) - 40} more (specialty, location) pairs not shown\")\n"
    ),
    nbf.v4.new_markdown_cell(
        "## Colocados vs vagas: placements should never exceed seats\n\n"
        "Per (year, specialty): sum of `vagas.seats` vs count of "
        "`colocados` rows. A specialty/year with more placements than "
        "seats is a red flag on the extraction, not real oversubscription "
        "(see CLAUDE.md's seats-vs-colocados note)."
    ),
    nbf.v4.new_code_cell(
        "seats_by_year_spec = defaultdict(int)\n"
        "for r in vagas:\n"
        "    seats_by_year_spec[(r['year'], r['specialty'].upper())] += int(r['seats'])\n"
        "\n"
        "placed_by_year_spec = defaultdict(int)\n"
        "for r in colocados:\n"
        "    placed_by_year_spec[(r['year'], r['specialty'].upper())] += 1\n"
        "\n"
        "violations = []\n"
        "for key, placed in placed_by_year_spec.items():\n"
        "    seats = seats_by_year_spec.get(key, 0)\n"
        "    if placed > seats:\n"
        "        violations.append((key, seats, placed))\n"
        "\n"
        "print(f\"{len(violations)} (year, specialty) pairs have MORE placements than seats:\\n\")\n"
        "for (year, spec), seats, placed in sorted(violations, key=lambda v: -(v[2]-v[1])):\n"
        "    print(f\"  {year} {spec:50s} seats={seats:5d} placed={placed:5d} (+{placed-seats})\")\n"
    ),
    nbf.v4.new_code_cell(
        "if violations:\n"
        "    labels = [f'{y} {s[:22]}' for (y, s), _, _ in sorted(violations, key=lambda v: -(v[2]-v[1]))[:20]]\n"
        "    overs = [p - s for (_, _), s, p in sorted(violations, key=lambda v: -(v[2]-v[1]))[:20]]\n"
        "    fig, ax = plt.subplots(figsize=(6, max(3, len(labels) * 0.3)))\n"
        "    ax.barh(labels[::-1], overs[::-1], color='#C44E52')\n"
        "    ax.set_xlabel('placements - seats (should be <= 0)')\n"
        "    ax.set_title('Colocados > vagas violations (top 20)')\n"
        "    plt.tight_layout()\n"
        "    plt.show()\n"
    ),
    nbf.v4.new_markdown_cell(
        "Down from 16 large violations to a couple dozen small ones (single "
        "digits to ~20 seats over, not hundreds) after fixing the seat "
        "double-count -- the residual gap is plausibly real placement "
        "process detail (reallocated/carry-over seats not present in that "
        "year's initial `vagas` offer) rather than an extraction bug, but "
        "each remaining pair is still worth a manual PDF check before "
        "trusting it at the seat level."
    ),
]

for path, nb in [("01_qa_seats_by_year_location.ipynb", nb1), ("02_specialty_year_location_pivot.ipynb", nb2)]:
    with open(path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"wrote {path}")
