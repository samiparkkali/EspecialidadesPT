"""FastAPI backend serving the processed vagas/colocados data.

Reads the CSVs produced by extract_vagas.py / extract_colocados.py (via
`make process`) into pandas DataFrames at startup and serves them filtered
by query params. No database -- the dataset is small (a few thousand rows)
and rebuilt from source PDFs, not written to at request time.

Run: uvicorn backend.api:app --reload
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

app = FastAPI(title="Especialidades PT API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


vagas_df = _load_csv("vagas.csv")
colocados_df = _load_csv("colocados.csv")


@app.get("/api/specialties")
def list_specialties() -> list[str]:
    specialties = pd.concat(
        [vagas_df.get("specialty", pd.Series(dtype=str)),
         colocados_df.get("specialty", pd.Series(dtype=str))]
    ).dropna().unique().tolist()
    return sorted(specialties)


@app.get("/api/vagas")
def get_vagas(
    specialty: str | None = None,
    region: str | None = None,
    institution: str | None = None,
    year: int | None = None,
) -> list[dict]:
    df = vagas_df
    if specialty:
        df = df[df["specialty"] == specialty]
    if region:
        df = df[df["region"] == region]
    if institution:
        df = df[
            (df["institution"] == institution)
            | (df["canonical_institution"] == institution)
        ]
    if year:
        df = df[df["year"] == year]
    return df.to_dict(orient="records")


@app.get("/api/vagas/evolution")
def vagas_evolution(
    specialty: str | None = None,
    canonical_institution: str | None = None,
) -> list[dict]:
    """Seats per year, optionally filtered -- the main chart data source."""
    df = vagas_df[vagas_df["institution"].notna() & (vagas_df["institution"] != "")]
    if specialty:
        df = df[df["specialty"] == specialty]
    if canonical_institution:
        df = df[df["canonical_institution"] == canonical_institution]
    grouped = df.groupby("year", as_index=False)["seats"].sum()
    return grouped.to_dict(orient="records")


@app.get("/api/colocados")
def get_colocados(
    specialty: str | None = None,
    institution: str | None = None,
    year: int | None = None,
) -> list[dict]:
    df = colocados_df
    if specialty:
        df = df[df["specialty"] == specialty]
    if institution:
        df = df[
            (df["institution"] == institution)
            | (df["canonical_institution"] == institution)
        ]
    if year:
        df = df[df["year"] == year]
    return df.to_dict(orient="records")


@app.get("/api/cutoffs")
def get_cutoffs(specialty: str | None = None) -> list[dict]:
    """Last (highest = worst) ordering number placed per specialty/institution/year.

    This is the historical "cutoff" a candidate needed to beat to get in --
    the basis for the ordering-number prediction endpoint below.
    """
    df = colocados_df
    if specialty:
        df = df[df["specialty"] == specialty]
    grouped = (
        df.groupby(["year", "specialty", "canonical_institution"], as_index=False)
        .agg(
            last_ordering_number=("ordering_number", "max"),
            placements=("ordering_number", "count"),
        )
    )
    return grouped.to_dict(orient="records")


@app.get("/api/predict")
def predict(ordering_number: int = Query(..., gt=0)) -> list[dict]:
    """For each specialty/institution, the years where this ordering number
    would have been good enough (ordering_number <= that year's last/worst
    placed ordering number), plus the average cutoff across all years
    currently in the dataset.

    Shown per-year rather than only as an average, since the cutoff can
    vary a lot year to year -- accuracy improves automatically as more
    years' colocados data get parsed and added to
    data/processed/colocados.csv.
    """
    if colocados_df.empty:
        return []

    per_year_cutoff = (
        colocados_df.groupby(["specialty", "canonical_institution", "year"])
        ["ordering_number"]
        .max()
        .reset_index()
        .rename(columns={"ordering_number": "cutoff"})
    )

    results = []
    for (specialty, institution), group in per_year_cutoff.groupby(
        ["specialty", "canonical_institution"]
    ):
        eligible_years = sorted(
            int(y) for y in group.loc[group["cutoff"] >= ordering_number, "year"]
        )
        if not eligible_years:
            continue
        results.append(
            {
                "specialty": specialty,
                "canonical_institution": institution,
                "eligible_years": eligible_years,
                "total_years": len(group),
                "avg_cutoff": round(group["cutoff"].mean()),
            }
        )

    results.sort(key=lambda r: (-len(r["eligible_years"]), r["avg_cutoff"]))
    return results


@app.get("/api/health")
def health() -> dict:
    return {
        "vagas_rows": len(vagas_df),
        "colocados_rows": len(colocados_df),
        "vagas_years": sorted(vagas_df["year"].unique().tolist()) if not vagas_df.empty else [],
        "colocados_years": sorted(colocados_df["year"].unique().tolist()) if not colocados_df.empty else [],
    }
