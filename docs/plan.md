# Overall Project Plan

## Goals

1. **Learn** data engineering end to end: ingestion, transformations and business logic, database management, and running a pipeline.
2. **Use** the data: a personal oncology landscape database.

Questions the database should answer:

- Which modalities and targets are being researched in each tumor type, by which companies, in which patient populations
- (Long term) What readouts showed for each drug, and the probability of success for compounds with the same modality, target and population

## Working Model

Each unit of work goes through: **understand → design → build → verify → record**. Notes from each unit are in [learning/](learning/).

## Roadmap

- [ ] **Phase 0: Architecture review** ← current
  - [x] A. Raw layer ([notes](learning/01-raw.md))
  - [x] B. Staging ([notes](learning/02-staging.md))
  - [ ] C. Reference and master (entity resolution) ← next
  - [ ] D. The study hub and data modeling
  - [ ] E. Marts and probability of success
  - [ ] F. Orchestration and operations
- [ ] **Phase 1: Trustworthy foundation**: dedupe staging, stable sponsor IDs, re-runnable steps
  - Known issues: staging SQL reads every raw snapshot instead of the latest per `nct_id` (latent while there's one fetch run); `sponsor_xwalk.score` is never written; no refresh script for `staging.interventions`; `ingest` stores only the first page's URL
- [ ] **Phase 2: Study layer**: phase, status, dates, indications, arms, links to sponsors and compounds; modality, target and population
- [ ] **Phase 3: Widen scope and load incrementally**: all of oncology, historical trials, only changed studies
- [ ] **Phase 4: Transformations in dbt**: tests, docs, lineage
- [ ] **Phase 5: Orchestration and monitoring**: scheduled runs, retries, data quality alerts
- [ ] **Phase 6: Efficacy evidence**: posted results, publications
- [ ] **Phase 7: Make it usable**: landscape queries, dashboard, review workflow

# History

## Stage 1: Initial Discovery (Complete)

- Parse JSON response into a tabular structure
- Test write to supabase
- Refine complex JSON responses with custom functions

## Stage 2: Schema Definition (In Progress)

- Define the database schema with tables for compounds, studies and sponsors 
- Create schema documentation 
- Develop pipeline architecture for the build

## Stage 3: Implementation (Up Next)

- Build the defined schema from stage 1
- Automation the ELT pipeline with scheduled jobs

# Oustanding Tasks

- [x] Create a raw layer to store the unprocessed JSON response (land raw tables in supabase)
- [x] Build the schema structure for the studies
- [x] Create an algorithm for mastering sponsor names
- [x] Build the crosswalk table for sponsor names
- [x] Develop algorithm for mastering compound names
- [x] Package existing code into standalone modules in src

# Future Extensions

- [] Change blocking technique in the sponsor mastering algorithm from established candidates to embedding ANN
- [] Build an agent to validate master data decisions
