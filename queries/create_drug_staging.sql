/*
Query that processes the raw response table into a staging
table for the interventions used in the trials.
*/

create table staging.interventions as
select r.nct_id,
       d ->> 'name' as drug,
       d ->> 'type' as type,
       d ->> 'description' as drug_description,
       d ->> 'otherNames' as other_info
from raw.raw_responses r,
     jsonb_array_elements(
       coalesce(r.raw_json #> '{protocolSection,armsInterventionsModule,interventions}', '[]'::jsonb)
     ) d;