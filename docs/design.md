# Pipeline Architecture

The program will contain a few modules that will be replicated for each object type:

- Requester: makes requests to the API. Handles connection issues, search parameters and pagination
- Response parser: create a class that parses the API response from clinicaltrials.gov, performs data validation / cleanin and packages the processed results in a tabular structure
- Writer: pushes the parsed data to the database

# Schema Design

There are three related objects that I want to create tables for: sponsors, compounds and studies. Each object will be anchored by a master table that contains the master records, primary keys and foreign keys for the object. Supplemental tables will supply additional attributes and facts for the main objects.

## Study-Related Schema

I plan to build the following study-related tables:

study_master:
  - nct_id (primary key)
  - study_title
  - study_long_title
  - sponsor_id (foreign key)
  - compound_id

study_design (long table where each arm is a record):
  - NCT_id (foreign key)
  - arm_id (primary key)
  - compound_id (foreign_key)

study_sponsors_collabs:

study_endpoints:

study_dates:

study_indications:

## Compound-Related Schema

compound_master:
  - compound_id