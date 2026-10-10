create schema if not exists staging;

create table staing.sponsors as
select nct_id, 
       'lead' as role,
       raw_json #>> '{protocolSection,sponsorCollaboratorsModule,leadSponsor,name}'  as raw_name,
       raw_json #>> '{protocolSection,sponsorCollaboratorsModule,leadSponsor,class}' as sponsor_class
from raw.raw_responses
union all
select r.nct_id, 
       'collaborator' as role,
       c ->> 'name' as raw_name,
       c ->> 'class' as sponsor_class
from raw.raw_responses r,
     jsonb_array_elements(
       coalesce(r.raw_json #> '{protocolSection,sponsorCollaboratorsModule,collaborators}', '[]'::jsonb)
     ) c;