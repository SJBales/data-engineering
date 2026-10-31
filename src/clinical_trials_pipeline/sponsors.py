"""
Master sponsor and collaborator names from staging.sponsors.

Steps:
  1. exact     - names that share a strict key (accents, punctuation and legal
                 suffixes removed) form one cluster
  2. fuzzy     - each cluster is compared to clusters with more mentions and the
                 same sponsor class; >= AUTO_SCORE merges automatically,
                 >= REVIEW_SCORE goes to output/sponsor_review_pairs.csv
  3. master    - one master record per merged cluster, named after its most
                 mentioned raw name; every raw name gets a crosswalk row

Usage:
    uv run python -m clinical_trials_pipeline.sponsors           # dry run + review CSV
    uv run python -m clinical_trials_pipeline.sponsors --write   # rebuild master tables
"""

import argparse
import re
import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process
from sqlalchemy import text
from sqlalchemy.engine import Engine

from clinical_trials_pipeline.config import OUTPUT_DIR
from clinical_trials_pipeline.db import get_engine

# Sets of strings to strip from sponsor and collaborator names
LEGAL = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited",
         "llc", "lp", "plc", "gmbh", "ag", "sa", "nv", "bv", "kk"}
GENERIC = {"pharmaceuticals", "pharma", "therapeutics", "biosciences", "biopharma",
           "labs", "laboratories", "laboratory", "holdings", "group"}

AUTO_SCORE, REVIEW_SCORE = 92, 80

PAIR_COLUMNS = ["source_cluster", "target_cluster", "fuzzy_score", "source_name", "target_name"]


def create_sponsor_tokens(sponsor_name: str) -> list[str]:
    """Remove accents and non-ASCII characters, lower-case, and replace
    punctuation with spaces. Returns the name's tokens."""
    s = unicodedata.normalize("NFKD", sponsor_name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return s.split()


def create_strict_key(sponsor_name: str) -> str:
    """Tokens without legal suffixes ('Pfizer Inc.' -> 'pfizer')."""
    return " ".join(t for t in create_sponsor_tokens(sponsor_name) if t not in LEGAL)


def create_loose_key(sponsor_name: str) -> str:
    """Tokens without legal suffixes or generic industry words, for fuzzy matching."""
    return " ".join(t for t in create_sponsor_tokens(sponsor_name) if t not in LEGAL | GENERIC)


def load_sponsor_names(engine: Engine) -> pd.DataFrame:
    """Distinct raw names with mention counts, most mentioned first."""
    return pd.read_sql(
        """select raw_name,
                  sponsor_class,
                  count(*) as total_mentions
           from staging.sponsors
           where raw_name is not null
           group by raw_name, sponsor_class
           order by count(*) desc""",
        engine,
    )


def cluster_exact(names: pd.DataFrame) -> pd.DataFrame:
    """Add strict/loose keys and an exact-match cluster id."""
    names = names.assign(strict_key=names.raw_name.map(create_strict_key),
                         loose_key=names.raw_name.map(create_loose_key))
    return names.assign(cluster=names.groupby("strict_key").ngroup())


def find_fuzzy_pairs(names: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Greedy match of each cluster to a more established cluster of the same class.

    Returns (auto_pairs, review_pairs).
    """
    # names is ordered by mentions, so the first row of a cluster is its representative
    reps = names.drop_duplicates("cluster")
    auto_pairs, review_pairs = [], []

    for row in reps.itertuples():
        established = reps[reps.total_mentions > row.total_mentions]
        if established.empty:
            continue
        best = process.extractOne(row.loose_key, established.loose_key.to_list(),
                                  scorer=fuzz.token_sort_ratio)
        if not best:
            continue
        _, score, idx = best
        target = established.iloc[idx]
        if row.sponsor_class != target.sponsor_class:
            continue
        rec = (row.cluster, target.cluster, score, row.raw_name, target.raw_name)
        if score >= AUTO_SCORE:
            auto_pairs.append(rec)
        elif score >= REVIEW_SCORE:
            review_pairs.append(rec)

    return (pd.DataFrame(auto_pairs, columns=PAIR_COLUMNS),
            pd.DataFrame(review_pairs, columns=PAIR_COLUMNS))


def resolve_clusters(names: pd.DataFrame, auto_pairs: pd.DataFrame) -> pd.Series:
    """Final cluster for each row after applying auto merges (following chains,
    e.g. A -> B -> C puts A in C)."""
    target = dict(zip(auto_pairs.source_cluster, auto_pairs.target_cluster, strict=True))

    def final(cluster: int) -> int:
        seen = {cluster}
        # targets always have more mentions, so chains can't loop; `seen` is a guard
        while cluster in target and target[cluster] not in seen:
            cluster = target[cluster]
            seen.add(cluster)
        return cluster

    return names.cluster.map(final)


def build_master(names: pd.DataFrame,
                 auto_pairs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (master records, crosswalk) keyed on canonical_name."""
    names = names.assign(final_cluster=resolve_clusters(names, auto_pairs))
    reps = names.drop_duplicates("final_cluster").set_index("final_cluster")
    names["canonical_name"] = names.final_cluster.map(reps.raw_name)

    fuzzy_score = auto_pairs.set_index("source_cluster").fuzzy_score
    names["match_method"] = "strict_key"
    names.loc[names.cluster != names.final_cluster, "match_method"] = "fuzzy_auto"
    names.loc[names.raw_name == names.canonical_name, "match_method"] = "canonical"
    names["score"] = names.cluster.map(fuzzy_score).where(names.match_method == "fuzzy_auto")

    master = reps.reset_index()[["raw_name", "sponsor_class"]].rename(
        columns={"raw_name": "canonical_name", "sponsor_class": "class"})
    # a raw name can appear under two sponsor classes; it gets one crosswalk row
    xwalk = names.drop_duplicates("raw_name")[["raw_name", "canonical_name",
                                               "match_method", "score"]]
    return master, xwalk


def write_master(engine: Engine, master: pd.DataFrame, xwalk: pd.DataFrame) -> None:
    """Rebuild master.sponsor and master.sponsor_xwalk in one transaction.

    sponsor_ids are reassigned on every rebuild; fine while nothing references them yet.
    """
    with engine.begin() as conn:
        conn.execute(text("truncate master.sponsor_xwalk, master.sponsor restart identity"))
        master.to_sql("sponsor", conn, schema="master", if_exists="append", index=False)
        ids = pd.read_sql(text("select sponsor_id, canonical_name from master.sponsor"), conn)
        (xwalk.merge(ids, on="canonical_name")[["sponsor_id", "raw_name", "match_method"]]
         .to_sql("sponsor_xwalk", conn, schema="master", if_exists="append", index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="rebuild the master tables")
    args = parser.parse_args()

    engine = get_engine()
    names = cluster_exact(load_sponsor_names(engine))
    auto_pairs, review_pairs = find_fuzzy_pairs(names)
    master, xwalk = build_master(names, auto_pairs)

    review_path = OUTPUT_DIR / "sponsor_review_pairs.csv"
    review_pairs.assign(decision=None).to_csv(review_path, index=False)

    print(f"{names.raw_name.nunique()} raw names -> {len(master)} master sponsors")
    print(xwalk.match_method.value_counts().to_string())
    print(f"{len(review_pairs)} pairs for review -> {review_path}")

    if args.write:
        write_master(engine, master, xwalk)
        print("Rebuilt master.sponsor and master.sponsor_xwalk")


if __name__ == "__main__":
    main()
