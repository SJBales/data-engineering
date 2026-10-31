"""
Pull studies from the ClinicalTrials.gov v2 API and land them unchanged in
raw.raw_responses (one row per study per fetch).

Usage:
    uv run python -m clinical_trials_pipeline.ingest            # dry run: fetch and count
    uv run python -m clinical_trials_pipeline.ingest --write    # append to raw.raw_responses
"""

import argparse
from datetime import UTC, datetime

import pandas as pd
import requests
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from clinical_trials_pipeline.db import get_engine

API_URL = "https://clinicaltrials.gov/api/v2/studies"

DEFAULT_PARAMS = {
    "query.cond": "non-small cell lung cancer",
    "filter.advanced": "AREA[StartDate]2022",
}
PAGE_SIZE = 1000   # API maximum

RAW_COLUMNS = ["nct_id", "raw_json", "fetched_at", "params", "response_url"]


def fetch_studies(params: dict) -> tuple[list[dict], str]:
    """Return every study matching `params`, following nextPageToken, plus the
    first page's URL for lineage."""
    studies, first_url, token = [], None, None
    while True:
        page_params = {**params, "pageSize": PAGE_SIZE}
        if token:
            page_params["pageToken"] = token
        response = requests.get(API_URL, params=page_params, timeout=60)
        response.raise_for_status()
        first_url = first_url or response.url
        body = response.json()
        studies.extend(body["studies"])
        token = body.get("nextPageToken")
        if not token:
            return studies, first_url


def raw_builder(studies: list[dict], params: dict, response_url: str) -> pd.DataFrame:
    """Build raw-layer rows (one per study) from ClinicalTrials.gov API studies."""
    fetched_at = datetime.now(UTC)
    params = dict(params)  # snapshot, so later mutation doesn't leak into stored rows

    return pd.DataFrame(
        [
            {
                "nct_id": s["protocolSection"]["identificationModule"]["nctId"],
                "raw_json": s,
                "fetched_at": fetched_at,
                "params": params,
                "response_url": response_url,
            }
            for s in studies
        ],
        columns=RAW_COLUMNS,
    )


def write_raw(engine: Engine, raw_table: pd.DataFrame) -> None:
    raw_table.to_sql(name="raw_responses",
                     schema="raw",
                     con=engine,
                     if_exists="append",
                     index=False,
                     dtype={"raw_json": JSONB, "params": JSONB},
                     method="multi",
                     chunksize=500)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="append to raw.raw_responses")
    args = parser.parse_args()

    studies, url = fetch_studies(DEFAULT_PARAMS)
    raw_table = raw_builder(studies, DEFAULT_PARAMS, url)
    print(f"Fetched {len(raw_table)} studies")

    if args.write:
        write_raw(get_engine(), raw_table)
        print("Appended to raw.raw_responses")


if __name__ == "__main__":
    main()
