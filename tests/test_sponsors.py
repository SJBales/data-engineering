import pandas as pd

from clinical_trials_pipeline.sponsors import (
    PAIR_COLUMNS,
    build_master,
    cluster_exact,
    create_loose_key,
    create_strict_key,
)


def test_strict_key_drops_legal_suffixes_and_accents():
    assert create_strict_key("Hoffmann-La Roche Ltd.") == "hoffmann la roche"
    assert create_strict_key("Société Générale SA") == "societe generale"


def test_loose_key_also_drops_generic_words():
    assert create_loose_key("Jiangsu Hengrui Pharmaceuticals Co., Ltd.") == "jiangsu hengrui"


def names_frame(rows):
    return cluster_exact(pd.DataFrame(rows, columns=["raw_name", "sponsor_class",
                                                     "total_mentions"]))


def test_exact_cluster_maps_every_raw_name_to_most_mentioned():
    names = names_frame([("Pfizer", "INDUSTRY", 10), ("Pfizer Inc.", "INDUSTRY", 2)])
    master, xwalk = build_master(names, pd.DataFrame(columns=PAIR_COLUMNS))

    assert master.canonical_name.tolist() == ["Pfizer"]
    assert dict(zip(xwalk.raw_name, xwalk.match_method, strict=True)) == {
        "Pfizer": "canonical", "Pfizer Inc.": "strict_key"}


def test_auto_pairs_merge_and_follow_chains():
    names = names_frame([("AstraZeneca", "INDUSTRY", 10),
                         ("Astra Zeneca AB", "INDUSTRY", 5),
                         ("Astra-Zeneca Pharma", "INDUSTRY", 1)])
    c = dict(zip(names.raw_name, names.cluster, strict=True))
    # chain: Pharma -> AB -> AstraZeneca
    auto = pd.DataFrame([(c["Astra-Zeneca Pharma"], c["Astra Zeneca AB"], 95, "", ""),
                         (c["Astra Zeneca AB"], c["AstraZeneca"], 93, "", "")],
                        columns=PAIR_COLUMNS)
    master, xwalk = build_master(names, auto)

    assert master.canonical_name.tolist() == ["AstraZeneca"]
    assert set(xwalk.canonical_name) == {"AstraZeneca"}
    assert xwalk.set_index("raw_name").loc["Astra Zeneca AB", "score"] == 93
