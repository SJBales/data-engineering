# data-engineering
Practicing the end-to-end workflows of data engineering (ETL)

# Project Overview

I am creating a database of compounds used in the treatment of cancer. I want to easily be able to understand all assets that are going through development, who is developing them, for what indication, where they are in the development lifecycle, and any evidence on their efficacy.

- Extract clinical trial data from clinicaltrials.gov
- Load raw data to supabase (or another cloud storage provider)
- Create transformation layers using dbt to process the raw data into useful tables
- Orchestrate jobs to pull on a regular basis

# Data Tables

See docs/design.md for detailed information on the schema design.