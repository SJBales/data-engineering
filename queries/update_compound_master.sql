/*
Merge the latest matching run (staging.compound_candidates /
staging.compound_xwalk_candidates, written by clinical_trials_pipeline.compounds) into
the master tables. compound_ids are stable across runs and reviewed mappings
are never overwritten.
*/

begin;

insert into master.compound (compound_key, canonical_name, inn, chembl_id, molecule_type, max_phase, source)
select compound_key, canonical_name, inn, chembl_id, molecule_type, max_phase, source
from staging.compound_candidates
on conflict (compound_key) do update
    set canonical_name = excluded.canonical_name,
        inn            = excluded.inn,
        chembl_id      = excluded.chembl_id,
        molecule_type  = excluded.molecule_type,
        max_phase      = excluded.max_phase,
        source         = excluded.source;

-- re-derive automatic mappings; anything a person has reviewed is kept
delete from master.compound_xwalk where not reviewed;

insert into master.compound_xwalk (raw_name, compound_id, match_method, matched_text, score)
select c.raw_name, m.compound_id, c.match_method, c.matched_text, c.score
from staging.compound_xwalk_candidates c
join master.compound m using (compound_key)
on conflict (raw_name, compound_id) do nothing;

commit;
