.PHONY: venv install process report frontend-install frontend-dev frontend-build api clean

VENV := .venv
PY := $(VENV)/Scripts/python.exe
PIP := $(VENV)/Scripts/pip.exe

venv:
	python -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt

# Parses every source PDF it can (native-text ones directly; scanned ones
# via backend/ocr_convert.py's cached OCR output) into data/processed/*.csv,
# then exports the same data as frontend/public/data/*.json for the static
# site build.
process:
	$(PY) backend/build_dataset.py

# Dumps extracted text per source PDF + data/processed/REPORT.md (year/
# status verification, row counts, self-consistency checks).
report:
	$(PY) backend/build_report.py

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Local FastAPI backend (optional -- the deployed static site doesn't need
# this, see frontend/src/hooks/useDataset.js and CLAUDE.md).
api: install
	$(VENV)/Scripts/uvicorn.exe backend.api:app --reload

clean:
	rm -rf data/processed/*.csv data/processed/*.json data/processed/REPORT.md data/processed/extracted_text
	rm -rf frontend/public/data/*.json
	rm -rf frontend/dist
