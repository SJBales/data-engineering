"""
Flatten raw study JSON into one row per study (the future study master).

Work in progress: there is no study table to write to yet, so this module only
builds the DataFrame.

Usage:
    uv run python -m clinical_trials_pipeline.studies    # preview from raw.raw_responses
"""

import pandas as pd
from sqlalchemy.engine import Engine

from clinical_trials_pipeline.db import get_engine


def parse_collaborators(sponsor_mod: dict) -> str | None:
    """Join collaborator names from the sponsorCollaboratorsModule."""
    names = [c.get("name") for c in sponsor_mod.get("collaborators", []) if c.get("name")]
    return ": ".join(names) or None


def extract_study_master(study: dict) -> dict:
    """Flatten one study from the API response into a single flat record."""
    protocol = study["protocolSection"]
    id_mod = protocol.get("identificationModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    cond_mod = protocol.get("conditionsModule", {})
    outcome_mod = protocol.get("outcomesModule", {})
    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})

    return {
        "nct_id": id_mod.get("nctId"),
        "study_title": id_mod.get("briefTitle"),
        "study_long_title": id_mod.get("officialTitle"),
        "study_acronym": id_mod.get("acronym"),
        "lead_sponsor": sponsor_mod.get("leadSponsor", {}).get("name"),
        "collaborators": parse_collaborators(sponsor_mod),
        "endpoints": [o.get("measure") for o in outcome_mod.get("primaryOutcomes", [])],
        "status": status_mod.get("overallStatus"),
        "study_type": design_mod.get("studyType"),
        "conditions": cond_mod.get("conditions"),
    }


def build_study_master(engine: Engine) -> pd.DataFrame:
    """Study records from the latest fetch of each study in the raw layer."""
    raw = pd.read_sql(
        """select distinct on (nct_id) raw_json
           from raw.raw_responses
           order by nct_id, fetched_at desc""",
        engine,
    )
    return pd.DataFrame([extract_study_master(s) for s in raw.raw_json])


def main() -> None:
    studies = build_study_master(get_engine())
    print(studies.head().to_string())
    print(f"{len(studies)} studies")


if __name__ == "__main__":
    main()
