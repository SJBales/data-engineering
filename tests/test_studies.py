from clinical_trials_pipeline.ingest import RAW_COLUMNS, raw_builder
from clinical_trials_pipeline.studies import extract_study_master

STUDY = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "A study",
                                 "acronym": "ASTUDY"},
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Pfizer"},
            "collaborators": [{"name": "NCI"}, {"name": "MSKCC"}],
        },
        "outcomesModule": {"primaryOutcomes": [{"measure": "Overall survival"}]},
        "statusModule": {"overallStatus": "RECRUITING"},
        "designModule": {"studyType": "INTERVENTIONAL"},
        "conditionsModule": {"conditions": ["NSCLC"]},
    }
}


def test_extract_study_master():
    row = extract_study_master(STUDY)
    assert row["nct_id"] == "NCT00000001"
    assert row["lead_sponsor"] == "Pfizer"
    assert row["collaborators"] == "NCI: MSKCC"
    assert row["endpoints"] == ["Overall survival"]
    assert row["study_long_title"] is None


def test_extract_study_master_without_collaborators():
    study = {"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}}}
    assert extract_study_master(study)["collaborators"] is None


def test_raw_builder_one_row_per_study():
    params = {"query.cond": "nsclc"}
    raw = raw_builder([STUDY], params, "https://example.org")
    assert raw.columns.tolist() == RAW_COLUMNS
    assert raw.nct_id.tolist() == ["NCT00000001"]
    params["query.cond"] = "changed"
    assert raw.params[0] == {"query.cond": "nsclc"}
