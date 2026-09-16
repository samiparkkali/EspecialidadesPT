# CLAUDE.md

Guidance for Claude Code (or any agent) working in this repo.

## What this is

A pipeline + app for analyzing the Portuguese medical specialty matching
process ("colocação de médicos"): yearly seat offers (`vagas-YYYY.pdf`, one
per specialty/region/hospital) and yearly placement results
(`YYYY-colocados.pdf` / `YYYY-colocações.pdf`, who got placed where, with
each candidate's national ordering number). The eventual goal is a UI where
a student enters their ordering number and sees which specialties they could
realistically get into, filterable by region/hospital.

## Layout

- `data/raw/vagas/` — yearly seat-offer PDFs, one row per
  specialty/region/hospital/seat-count. **The only source of "seats
  available"** — never derive a seat count from colocados (count of
  placements, or number of colocados rows). Vacancies routinely go
  unfilled, so colocados count is always <= vagas seats for a given
  specialty/institution/year; treating them as interchangeable
  overstates how competitive a specialty looks and understates leftover
  capacity. `vagas.csv`'s `seats` column is the only field that should
  ever be summed/charted as "seats"; colocados rows don't have one.
- `data/raw/colocacoes/` — yearly placement-result PDFs, one row per
  candidate/ordering-number/specialty/hospital placed into. Use this for
  who got placed and their ordering number/cutoff, not for how many
  seats existed.
- `data/processed/` — generated CSV/parquet from the pipeline. Not
  committed (git-ignored) — regenerate with `make process`.
- `docling/` — git submodule, a PDF→markdown conversion pipeline. Extend it
  in place (it's a real repo with its own history) rather than duplicating
  its logic here. Only actually needed for the scanned/image-only source
  PDFs (OCR path) — native-text PDFs are parsed directly in `backend/`
  without it, since that's both faster and more accurate for them.
- `backend/` — Python: PDF extraction, parsing into structured records,
  and an API serving the processed data to the frontend.
- `frontend/` — React + Vite app for browsing/filtering the data.

## Python conventions

- Python 3.12, dependencies pinned with `==` in `requirements.txt`.
- Use a per-project `.venv`, not a global install. Activate it before
  running anything (`source .venv/bin/activate` / `.venv\Scripts\activate`
  on Windows).
- Tests via `pytest`, in a top-level `tests/` dir, run with
  `python -m pytest tests/ -v` (running a test file directly with `python`
  does not invoke pytest's discovery).
- Catch and attribute errors per-item in a batch rather than aborting the
  whole run — one bad PDF shouldn't kill the other 9.
- Prefer a small dataclass/stats object summarizing a batch run over
  ad-hoc prints, so results can be asserted on in tests and printed as a
  report.
- Logging via a shared logger helper, not bare `print`, for anything
  beyond a one-off script's own output.

## Frontend conventions

- React (function components, hooks) + Vite, ESLint (`eslint.config.js`)
  must pass clean before considering a change done — run `npx eslint src`.
- CSS Modules per component (`Component.module.css`), no CSS-in-JS.
  Shared tokens (`--color-*`, `--radius`, `--transition`, fonts) live in
  `src/styles/variables.css` — extend or reuse those rather than
  hardcoding new colors/spacing inline.
- One component per directory (`src/components/Name/Name.jsx` +
  `Name.module.css`).
- No unnecessary comments; only explain non-obvious *why*. No emojis in
  code or UI copy unless explicitly asked.
- Verify every change with `npx eslint src` and `npm run build` before
  calling it done — don't just eyeball the diff.

## Working with the PDFs

- Confirm before trusting any extracted number: does the filename's year
  match the year printed inside the document, and for `colocacoes/` files,
  is the result marked as *definitivo* (final) rather than *provisório*
  (provisional)? Some years' filenames are inconsistent
  (`colocações` vs `colocados`) — don't infer status from the filename
  alone, check the document text.
- Before assuming OCR is needed: check whether the PDF actually has
  extractable native text first (`page.get_text()` non-empty, embedded
  Unicode is usually correct even if a terminal displays it as mojibake —
  verify with `ord(char)`, not by eyeballing console output). Only fall
  back to OCR (via the `docling` submodule) for pages that are genuinely
  scanned images (`page.get_text()` empty but `page.get_images()`
  non-empty).
- Each year's PDF can use a different layout (indent-based hierarchy vs.
  explicit "Subtotal"/"Total" labels, reading order, column headers) —
  don't assume one parser generalizes across years without checking.
- These are large PDFs (some 20-40MB, official government tables). Test
  extraction logic against the smallest file first before running the
  full batch.
- Extracted data should be traceable back to its source file and page —
  don't silently merge/dedupe rows across years without keeping the
  source year as a column.
- Institution names are not stable across years — the 2024/2025 SNS
  reorganization merged many hospitals into "ULS <region>" entities.
  Always add a canonicalized institution column (see
  `backend/institution_mapping.py`) alongside the raw name before doing
  any cross-year aggregation or charting; never overwrite the raw name.

## General

- Never surface real student names/identifying data beyond what's already
  public in the official PDFs — the source documents are public results,
  but derived datasets/UI should still avoid surfacing anything beyond
  ordering number + specialty + hospital + region + year.
- Don't push to `main`/`master` or create commits unless explicitly asked.
- This repo intentionally nests multiple things (data, a git submodule,
  a Python backend, a React frontend) rather than being split into
  several repos — keep new tooling under the existing `backend/`/
  `frontend/`/`docling/` boundaries instead of adding new top-level repos.
