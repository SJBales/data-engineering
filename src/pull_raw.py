# For API calls and response parsin
import pandas as pd
import requests

# For connecting to Supabase
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv
import os

# For parsing responses
from datetime import datetime, timezone

# Hitting the clinicaltrials.gov API
url = "https://clinicaltrials.gov/api/v2/studies"

params = {"query.cond": "non-small cell lung cancer",
          "pageSize": 100,
          "filter.advanced": "AREA[StartDate]2022"}

response = requests.get(url, params)

study = response.json()

# Raw-layer columns
RAW_COLUMNS = ["nct_id", "raw_json", "fetched_at", "params", "response_url"]


def raw_builder(response: requests.Response, params: dict) -> pd.DataFrame:
    """Build raw-layer rows (one per study) from a
    ClinicalTrials.gov API response."""
    response.raise_for_status()
    studies = response.json()["studies"]

    fetched_at = datetime.now(timezone.utc)
    params = dict(params)

    return pd.DataFrame(
        [
            {
                "nct_id": s["protocolSection"]["identificationModule"]["nctId"],
                "raw_json": s,
                "fetched_at": fetched_at,
                "params": params,
                "response_url": response.url,
            }
            for s in studies
        ],
        columns=RAW_COLUMNS,
    )


# Connecting to Supabase
load_dotenv()

client = create_engine(os.getenv("SUPABASE_PROJECT_URL"))

raw_table = raw_builder(response, params)

# Writing to Supabase
raw_table.to_sql(name="raw_responses",
                 schema="raw",
                 con=client,
                 if_exists="append",
                 index=False,
                 dtype={"raw_json": JSONB, "params": JSONB},
                 method="multi",
                 chunksize=500)
