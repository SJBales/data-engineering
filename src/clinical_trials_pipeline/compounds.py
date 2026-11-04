"""
Master the compound names in ClinicalTrials.gov interventions against
INN-anchored reference data (ChEMBL synonyms + WHO Proposed INN lists).

Steps:
  1. reference - ChEMBL clinical-stage molecules (salts rolled up to their parent)
                 plus WHO INNs that ChEMBL doesn't have yet
  2. matching  - scan each distinct intervention string for known names in 1-4
                 token windows, then classify what's left over: research codes
                 become new compounds, INN-shaped words go to review, anything
                 else is a generic term (chemotherapy, placebo, ...)
  3. load      - candidates are merged into master.compound / compound_xwalk by
                 queries/update_compound_master.sql, so compound_ids and reviewed
                 mappings survive re-runs

Usage:
    uv run python -m clinical_trials_pipeline.compounds                   # dry run -> output/*.csv
    uv run python -m clinical_trials_pipeline.compounds --write           # also load Supabase
    uv run python -m clinical_trials_pipeline.compounds --refresh-chembl  # re-pull ChEMBL
"""

import argparse
import re
from dataclasses import dataclass, field

import pandas as pd
import requests
from rapidfuzz import fuzz, process
from sqlalchemy import text
from sqlalchemy.engine import Engine

from clinical_trials_pipeline.config import OUTPUT_DIR, QUERIES_DIR
from clinical_trials_pipeline.db import get_engine, run_sql_file

CHEMBL_CACHE = OUTPUT_DIR / "chembl_synonyms.csv"
WHO_INN = OUTPUT_DIR / "inn_names.csv"   # from clinical_trials_pipeline.inn
UPDATE_SQL = QUERIES_DIR / "update_compound_master.sql"

CHEMBL_BASE = "https://www.ebi.ac.uk"
CHEMBL_FILTERS = ["max_phase__gte=0.5", "molecule_synonyms__syn_type=INN"]
CHEMBL_FIELDS = ("molecule_chembl_id,pref_name,max_phase,molecule_type,"
                 "molecule_hierarchy,molecule_synonyms")

COMPOUND_TYPES = ("DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT")

# Words that carry no compound identity: formulation, route, salts, trial-arm language,
# plus generic words that happen to be ChEMBL synonyms ('platinum', 'Choice' = warfarin)
STOP = set("""
injection injectable tablet tablets capsule capsules oral intravenous iv sc subcutaneous
intrathecal pill product solution concentrate infusion powder dose doses daily twice once
monotherapy therapy treatment group arm regimen standard high low plus and or with in
combination combined followed by of for the a to before after alone sequential each total
mesylate hydrochloride maleate sodium tosylate disodium sulfate citrate phosphate acetate
besylate succinate tartrate olamine placebo comparator test biosimilar
chemotherapy immunotherapy vaccine peptide peptides cells analog based bound
platinum albumin choice
""".split())

# Tokens that describe a target or isotope rather than name a compound
TARGET = re.compile(r"^(anti-|hla-|pd-?l?\d|ctla-?\d|cd\d+|her-?\d|il-?\d+|tlr\d|lag-?\d|"
                    r"tim-?\d|a2[ab]$)")
ISOTOPE = re.compile(r"^(zirconium|gallium|lutetium|actinium|technetium|yttrium|iodine|copper|"
                     r"lead|fluorine|radium|thorium|indium)-?\d+|^\d+[a-z]{1,2}$")   # '89Zr'
# A hit followed by one of these describes something else ("adenosine receptor antagonist",
# "triptolide analog")
TARGET_CONTEXT = {"receptor", "antagonist", "agonist", "inhibitor", "inhibitors", "pathway",
                  "analog", "analogue", "derivative"}

DOSE = re.compile(r"\b\d+(\.\d+)?\s?(mg|mcg|μg|ug|g|ml|mg/kg|mg/m2|iu)\b"
                  r"(\s*/\s*\d*\s*(ml|kg|m2))?", re.I)
SEP = re.compile(r"[\s,+/;:&()\[\]{}，；、（）]+")
INN_STEM = re.compile(r"(mab|tinib|nib|lib|rib|parib|platin|taxel|rubicin|sib|cept|tide|stat|"
                      r"vir|cel|gene|leukin|kin|mig|tug|bart|pag)$")
FUZZY_CUTOFF = 85


def key(s: str) -> str:
    """Lookup key: lowercase alphanumerics only, so 'MK-3475' == 'mk 3475' == 'MK3475'."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


# --------------------------------------------------------------------------- #
# 1. Reference data
# --------------------------------------------------------------------------- #

def fetch_chembl() -> pd.DataFrame:
    """One row per (molecule, synonym) for clinical-stage molecules and anything with an INN."""
    rows, seen = [], set()
    for filt in CHEMBL_FILTERS:
        url = f"{CHEMBL_BASE}/chembl/api/data/molecule.json?{filt}&limit=1000&only={CHEMBL_FIELDS}"
        while url:
            page = requests.get(url, timeout=90)
            page.raise_for_status()
            page = page.json()
            meta = page["page_meta"]
            print(f"  ChEMBL {filt}: {meta['offset']} / {meta['total_count']}")
            for m in page["molecules"]:
                if m["molecule_chembl_id"] in seen:
                    continue
                seen.add(m["molecule_chembl_id"])
                base = {
                    "chembl_id": m["molecule_chembl_id"],
                    "parent_chembl_id": (m["molecule_hierarchy"] or {}).get("parent_chembl_id")
                    or m["molecule_chembl_id"],
                    "pref_name": m["pref_name"],
                    "max_phase": m["max_phase"],
                    "molecule_type": m["molecule_type"],
                }
                if m["pref_name"]:
                    rows.append({**base, "synonym": m["pref_name"], "syn_type": "PREF_NAME"})
                for s in m["molecule_synonyms"]:
                    rows.append({**base, "synonym": s["molecule_synonym"],
                                 "syn_type": s["syn_type"]})
            nxt = meta["next"]
            url = CHEMBL_BASE + nxt if nxt else None
    return pd.DataFrame(rows)


def build_reference(chembl: pd.DataFrame, who: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (reference.compound, reference.compound_synonym) frames.

    ChEMBL salts/forms are keyed on their parent molecule, so 'osimertinib mesylate'
    and 'osimertinib' resolve to the same compound. WHO INNs are only added when
    ChEMBL doesn't already know the name.
    """
    chembl = chembl.assign(compound_key=chembl.parent_chembl_id)
    # Attributes come from the parent's own record when we have it
    chembl["is_parent"] = chembl.chembl_id == chembl.parent_chembl_id
    ranked = chembl.sort_values("is_parent", ascending=False)
    inn = (ranked[ranked.syn_type == "INN"].drop_duplicates("compound_key")
           .set_index("compound_key").synonym.str.lower())
    compounds = ranked.drop_duplicates("compound_key").set_index("compound_key")
    compounds = pd.DataFrame({
        "source": "chembl",
        "inn": inn.reindex(compounds.index),
        "pref_name": compounds.pref_name.str.lower(),
        "chembl_id": compounds.index,
        "molecule_type": compounds.molecule_type,
        "max_phase": pd.to_numeric(compounds.max_phase),
    })
    compounds["canonical_name"] = (compounds.inn.fillna(compounds.pref_name)
                                   .fillna(compounds.chembl_id)
                                   .str.replace(r"\s*\(?anhydrous\)?$", "", regex=True))
    compounds = compounds.drop(columns="pref_name").reset_index()

    synonyms = chembl[["compound_key", "synonym", "syn_type"]]

    known = set(synonyms.synonym.map(key))
    who = who[~who.inn_english.map(key).isin(known)]
    who_keys = "WHO:" + who.inn_english
    who_compounds = pd.DataFrame({
        "compound_key": who_keys, "source": "who", "inn": who.inn_english,
        "chembl_id": None, "molecule_type": None, "max_phase": None,
        "canonical_name": who.inn_english,
    })
    who_synonyms = pd.concat([
        pd.DataFrame({"compound_key": who_keys, "synonym": who[col], "syn_type": syn_type})
        for col, syn_type in [("inn_english", "INN"), ("inn_latin", "INN_LATIN"),
                              ("inn_french", "INN_FRENCH"), ("inn_spanish", "INN_SPANISH")]
    ])

    compounds = pd.concat([compounds, who_compounds], ignore_index=True)
    synonyms = pd.concat([synonyms, who_synonyms], ignore_index=True).dropna()
    synonyms = synonyms.assign(synonym_key=synonyms.synonym.map(key))
    synonyms = synonyms.drop_duplicates(["compound_key", "synonym", "syn_type"])
    return compounds[["compound_key", "source", "canonical_name", "inn", "chembl_id",
                      "molecule_type", "max_phase"]], synonyms


def build_lexicon(synonyms: pd.DataFrame) -> dict[str, str]:
    """synonym_key -> compound_key, keeping only unambiguous, meaningful keys."""
    s = synonyms[(synonyms.synonym_key.str.len() >= 3)
                 & ~synonyms.synonym_key.isin(STOP)
                 & ~synonyms.synonym.str.lower().str.match(TARGET)
                 # free-text synonyms: short ones ('PD-L1') are usually targets, long ones
                 # ('Natural killer cells') are descriptions that match generic arms
                 & ~((synonyms.syn_type == "OTHER")
                     & ((synonyms.synonym_key.str.len() <= 5)
                        | (synonyms.synonym.str.count(" ") >= 2)))]
    owners = s.groupby("synonym_key").compound_key.unique()
    ambiguous = owners[owners.str.len() > 1]
    if len(ambiguous):
        print(f"  {len(ambiguous)} synonyms map to more than one compound; excluded from matching")
    return owners[owners.str.len() == 1].str[0].to_dict()


# --------------------------------------------------------------------------- #
# 2. Matching
# --------------------------------------------------------------------------- #

@dataclass
class Scan:
    hits: dict[str, str] = field(default_factory=dict)   # compound_key -> matched text
    codes: list[str] = field(default_factory=list)       # research codes not in the lexicon
    names: list[str] = field(default_factory=list)       # INN-shaped words not in the lexicon


def tokenize(raw: str) -> list[str]:
    s = DOSE.sub(" ", re.sub(r"[™®©]", "", raw))
    return [t.strip("-.") for t in SEP.split(s) if t.strip("-.")]


def is_code(token: str) -> bool:
    k, low = key(token), token.lower()
    return (len(k) >= 4 and re.search(r"[a-z]", k) and re.search(r"\d", k)
            and not TARGET.match(low) and not ISOTOPE.match(low)) is True


def scan(raw: str, lexicon: dict[str, str]) -> Scan:
    """Find every known compound name in a free-text intervention string."""
    toks = tokenize(raw)
    low = [t.lower() for t in toks]
    covered = [False] * len(toks)
    result = Scan()

    # Longest windows first, so 'datopotamab deruxtecan' beats 'datopotamab'
    for size in (4, 3, 2, 1):
        for i in range(len(toks) - size + 1):
            if any(covered[i:i + size]):
                continue
            compound = lexicon.get(key("".join(low[i:i + size])))
            if not compound or TARGET_CONTEXT.intersection(low[i + size:i + size + 2]):
                continue
            result.hits.setdefault(compound, " ".join(toks[i:i + size]))
            covered[i:i + size] = [True] * size

    # Hyphenated forms such as 'nab-paclitaxel'
    for i, t in enumerate(low):
        if not covered[i] and "-" in t:
            for part in t.split("-"):
                if len(part) >= 5 and (compound := lexicon.get(key(part))):
                    result.hits.setdefault(compound, toks[i])
                    covered[i] = True

    i = 0
    while i < len(toks):
        if covered[i] or low[i] in STOP:
            i += 1
            continue
        # Codes written with a space: 'BI 765063', 'JAB 21822'
        if (toks[i].isalpha() and len(toks[i]) <= 5 and i + 1 < len(toks)
                and not covered[i + 1] and toks[i + 1].isdigit() and len(toks[i + 1]) >= 3):
            result.codes.append(f"{toks[i]} {toks[i + 1]}")
            i += 2
            continue
        if is_code(toks[i]):
            result.codes.append(toks[i])
        elif low[i].isalpha() and len(low[i]) >= 7 and INN_STEM.search(low[i]):
            result.names.append(low[i])
        i += 1
    return result


def parse_aliases(other_info) -> list[str]:
    if not isinstance(other_info, list):
        return []
    return [a.strip() for v in other_info for a in re.split(r"[;,]", str(v)) if a.strip()]


def match_interventions(interventions: pd.DataFrame, lexicon: dict[str, str],
                        compounds: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (compound candidates, xwalk candidates, review queue)."""
    drugs = (interventions[interventions.type.isin(COMPOUND_TYPES)]
             .dropna(subset=["drug"]).drop_duplicates("drug"))
    inn_choices = compounds.dropna(subset=["inn"])
    inn_choices = inn_choices[inn_choices.inn.str.isalpha()]
    inn_names, inn_keys = inn_choices.inn.tolist(), inn_choices.compound_key.tolist()

    xwalk, review, new_codes = [], [], {}
    for raw, other in zip(drugs.drug, drugs.other_info, strict=True):
        s = scan(raw, lexicon)
        method = "exact" if key(raw) in lexicon else "token_scan"
        for compound, matched in s.hits.items():
            xwalk.append((raw, compound, method, matched, 100))

        # A bare code whose other_info names one known compound is often that compound,
        # but other_info sometimes lists combination partners, so a person decides
        if not s.hits and len(s.codes) == 1:
            alias_hits = {c: t for a in parse_aliases(other)
                          for c, t in scan(a, lexicon).hits.items()}
            if len(alias_hits) == 1:
                (compound, matched), = alias_hits.items()
                review.append({"raw_name": raw, "category": "alias", "token": s.codes[0],
                               "suggestion": matched, "suggested_compound_key": compound})

        for code in s.codes:
            ck = f"CODE:{key(code)}"
            new_codes.setdefault(ck, code.upper())
            xwalk.append((raw, ck, "new_code", code, None))

        for name in s.names:
            best = process.extractOne(name, inn_names, scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF)
            review.append({
                "raw_name": raw,
                "category": "fuzzy" if best else "unreferenced_name",
                "token": name,
                "suggestion": best[0] if best else None,
                "suggested_compound_key": inn_keys[best[2]] if best else None,
                "score": round(best[1]) if best else None,
            })

        if not (s.hits or s.codes or s.names):
            review.append({"raw_name": raw, "category": "no_compound"})

    xwalk = pd.DataFrame(xwalk, columns=["raw_name", "compound_key", "match_method",
                                         "matched_text", "score"])
    code_compounds = pd.DataFrame({
        "compound_key": list(new_codes), "source": "research_code",
        "canonical_name": list(new_codes.values()),
    })
    candidates = pd.concat([compounds[compounds.compound_key.isin(xwalk.compound_key)],
                            code_compounds], ignore_index=True)
    review = pd.DataFrame(review, columns=["raw_name", "category", "token", "suggestion",
                                           "suggested_compound_key", "score"]).assign(decision=None)
    return candidates, xwalk, review


# --------------------------------------------------------------------------- #
# 3. Load
# --------------------------------------------------------------------------- #

def load(engine: Engine, compounds: pd.DataFrame, synonyms: pd.DataFrame,
         candidates: pd.DataFrame, xwalk: pd.DataFrame) -> None:
    with engine.begin() as conn:
        conn.execute(text("truncate reference.compound_synonym, reference.compound"))
        compounds.to_sql("compound", conn, schema="reference", if_exists="append",
                         index=False, method="multi", chunksize=1000)
        synonyms.to_sql("compound_synonym", conn, schema="reference", if_exists="append",
                        index=False, method="multi", chunksize=1000)
        candidates.to_sql("compound_candidates", conn, schema="staging", if_exists="replace",
                          index=False)
        xwalk.to_sql("compound_xwalk_candidates", conn, schema="staging", if_exists="replace",
                     index=False)
    run_sql_file(engine, UPDATE_SQL)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="load results into Supabase")
    parser.add_argument("--refresh-chembl", action="store_true", help="re-pull ChEMBL synonyms")
    args = parser.parse_args()

    engine = get_engine()

    if args.refresh_chembl or not CHEMBL_CACHE.exists():
        print("Fetching ChEMBL synonyms...")
        fetch_chembl().to_csv(CHEMBL_CACHE, index=False)
    chembl = pd.read_csv(CHEMBL_CACHE)
    compounds, synonyms = build_reference(chembl, pd.read_csv(WHO_INN))
    lexicon = build_lexicon(synonyms)
    print(f"Reference: {len(compounds)} compounds, {len(synonyms)} synonyms")

    interventions = pd.read_sql("select * from staging.interventions", engine)
    candidates, xwalk, review = match_interventions(interventions, lexicon, compounds)

    xwalk.to_csv(OUTPUT_DIR / "compound_xwalk_candidates.csv", index=False)
    review.to_csv(OUTPUT_DIR / "compound_review.csv", index=False)
    print(f"Matched: {xwalk.raw_name.nunique()} intervention strings -> "
          f"{xwalk.compound_key.nunique()} compounds")
    print(xwalk.match_method.value_counts().to_string())
    print(f"Review queue: {len(review)} rows -> {OUTPUT_DIR / 'compound_review.csv'}")
    print(review.category.value_counts().to_string())

    if args.write:
        load(engine, compounds, synonyms, candidates, xwalk)
        print("Loaded reference.compound*, master.compound and master.compound_xwalk")


if __name__ == "__main__":
    main()
