# Overall Project Plan

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
- [] Develop algorithm for mastering compound names
- [] Build staging tables for arms and study design
- [] Package existing code into standalone modules in src

# Future Extensions

- [] Change blocking technique in the sponsor mastering algorithm from established candidates to embedding ANN
- [] Build an agent to validate master data decisions
