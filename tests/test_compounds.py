from clinical_trials_pipeline.compounds import is_code, key, scan

LEXICON = {
    "pembrolizumab": "CHEMBL3137343",
    "keytruda": "CHEMBL3137343",
    "mk3475": "CHEMBL3137343",
    "carboplatin": "CHEMBL1351",
    "pemetrexed": "CHEMBL225072",
    "paclitaxel": "CHEMBL428647",
    "datopotamabderuxtecan": "CHEMBL4297939",
    "datopotamab": "CHEMBL_DATO",
    "adenosine": "CHEMBL477",
}


def test_key_ignores_case_and_punctuation():
    assert key("MK-3475") == key("mk 3475") == "mk3475"


def test_scan_finds_each_drug_in_a_combination():
    s = scan("Pembrolizumab + Carboplatin/Pemetrexed 500 mg/m2", LEXICON)
    assert set(s.hits) == {"CHEMBL3137343", "CHEMBL1351", "CHEMBL225072"}


def test_scan_prefers_longest_name():
    assert set(scan("Datopotamab Deruxtecan (Dato-DXd)", LEXICON).hits) == {"CHEMBL4297939"}


def test_scan_brand_and_code_resolve_to_one_compound():
    assert set(scan("KEYTRUDA® (MK-3475)", LEXICON).hits) == {"CHEMBL3137343"}


def test_scan_splits_hyphenated_formulation():
    assert set(scan("nab-paclitaxel", LEXICON).hits) == {"CHEMBL428647"}


def test_scan_skips_target_descriptions_and_keeps_codes():
    s = scan("Adenosine A2B Receptor Antagonist PBF-1129", LEXICON)
    assert s.hits == {}
    assert s.codes == ["PBF-1129"]


def test_scan_joins_codes_written_with_a_space():
    assert scan("BI 765063", LEXICON).codes == ["BI 765063"]


def test_is_code_excludes_targets_and_isotopes():
    assert is_code("NI-1801")
    assert not is_code("PD-1")
    assert not is_code("anti-PD-L1")
    assert not is_code("89Zr")
