# Schema Design

There are three related objects that I want to create tables for: sponsors, compounds and studies. Each object will be anchored by a master table that contains the master records, primary keys and foreign keys for the object. Supplemental tables will supply additional attributes and facts for the main objects.

I will persist the raw JSON response in a raw layer.

# Raw Layer

raw_response:
  - nct_id (primary key)
  - raw_json
  - params
  - response_url
  - fetched_at (primary key)

# Staging

sponsors:
  - nct_id
  - role
  - raw_name
  - sponsor_class

interventions:
  - nct_id
  - drug
  - type
  - drug_description
  - other_info

# Study Tables

I plan to build the following study-related tables:

study_master:
  - nct_id (primary key)
  - study_title
  - study_long_title
  - study_acronym
  - sponsor_id (foreign key)
  - compound_id (foreign key)
  - lead_sponsor
  - collaborator_id
  - collaborator_names
  - study_type
  - conditions

study_design (long table where each arm is a record):
  - nct_id (foreign key)
  - arm_id (primary key)
  - compound_id (foreign_key)

study_endpoints:
  - nct_id (foreign key)
  - primary_endpoint
  - secondary_endpoints
  - exploratory_endpoint

study_dates:
  - ncti_id (foreign key)
  - start_date
  - end_date

# Sponsor

sponsor_master:
  - sponsor_id (primary key)
  - sponsor_name
  - sponsor_country
  - sponsor_type

# Compound

compound_master:
  - compound_id (primary key)
  - compound_name
  - mechanism_of_action
  - target
  - modality
  - route_of_administration