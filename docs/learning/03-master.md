# Mastering

The core question is to determine if two entities are the same, and to create a single identifier for merged entities.

## Core Concepts

The matering flow follows a series of consistent steps:
Staging (raw names) --> matching raw names --> crosswalk (raw name --> ID) --> master (one row per entity)

And there are a few core concepts that run behind it:

## Steps In Entity Resolution

Objective: are two records refer to the same real-world thing? The process follows a sequence of steps:

1. Standardize --> clean values into a comparable form (lowercase, stripping punctucation and legal suffixes)
2. Block --> decide which pairs are worth comparing; not everything can be compared, otherwise the computation grows too large
3. Compare --> score how similar candidate pairs are; quantify similarity
4. Classify --> decide match, non-match or a review
5. Cluster --> turn pairwise matches into groups; must decide if a larger entity can be constructed out of identified pairs
6. Golden Record --> pick each group's name and attribute values; master row needs one value per field
7. Keep decisions --> store the mappings with stable ID's and protect human review decisions

### Standardize

Raw text, especially that collected from a wide range of entities over time, is likely to contain artifacts in the raw string that are irrelevant for deciding if entites are the same. For this project a four cleaning steps were used, sorted from most to least risky:

- Unicode and case: removing special characters and converting all text to lowercase
- Punctuation: removing punctuation controls for stylistic variances in data entry (e.g. Co. vs. Co)
- Legal suffixes: can be stylistic preference of the person entering the data to include the legal entity
- Generic industry words: decision to remove common generic words from company names to match on the likely highest differentiating terms in the string --> this is a judgement call

### Compare

Core idea: the comparison measures evidence, not resemblance. We want to answer the question of how surprising would this agreement be if the two records were different entities. In practice:

- Score evidence, not resemblance: rare agreement counts more
- Disagreement counts too: a distinctive word on only one side points away from a match
- Be clear what the evidence is about: a shared word can identify a family rather than one entity

### Classify

The classification step either rejects (non-match) a match, flags a possible match for review (review) or merges the pair automatically (match). A false merge corrupts master silently, a missed match leaves a viable duplicated and review costs human time. Strict auto-merge thresholds and low thresholds for review add manual burden to validating or rejecting entity matches. Current thresholds of 80 for review and 92 for match are guesses and will be tuned by hand-reviewing entities to identify matches.

Token or string matches have weaknesses as they can be corrupted by long strings with overlapping tokens diluting the total match score. Generic words can be stripped from strings so the most relevant tokens are left. Overdoing stripping generic words removes information that can be used to confirm or reject a match. Evidence rules like token veto (i.e. disagreement on a key token) and token-level matching reduce the dilution effect. Differences in token counts that autotrigger a manual review account for possible overlap of a smaller token series in a larger string.

## Cluster

Classify decides pairs. Cluster turns those pairs into groups. Following chains of pairs is single linkage. Creating a single group of pairwise comparisons has a weakness: links between more distant pairs can fall below the match threshold. For example, a group based on three records that are compared pairwise as A --> B --> C where each match is represented by an arrow. Each arrow could clear the threshold for the similarity score, but A --> C were never directly compared and it could fail to clear the threshold. To solve this, all possible matches in a group must be compared to create a complete linkage. Complete linkage stops a chain of weak links from merging different entities. The tradeoff is cost and splitting true groups. If a pairwise match fails to clear the threshold when comparing across the group but the entities are actually the same, a proper cluster could be split into a smaller group. Other methods like hierarchical clustering, graph methods and probabilistic models do not rely on single linkages and do not have the same limitation.
