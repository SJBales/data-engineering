# data-engineering
Practicing the end-to-end workflows of data engineering (ETL)

# Project Overview

- Extract clinical trial data from clinicaltrials.gov
- Load raw data to supabase (or similar inexpensive cloud provider)
- Create transformation layers using dbt to process the raw data into useful tables
- Orchestrate jobs to pull on a regular basis

# Data Tables

I am creating a database of compounds used in the treatment of cancer. I plan to build tables that detail the following:

- Sponsors of oncology trials (domcile, headquarters, etc.)
- Compounds
- Studies (completed, ongoing, etc)
- Data readouts

Each table will have a dedicated schema and may be expanded to a full dataset later.

## Compounds

- Compound name
- Mechanism of action
- Target
- Route of administration
