/*
Tables for compound mastering. Reference tables hold the full universe of known
compounds (ChEMBL clinical-stage molecules + WHO INNs not yet in ChEMBL); master
tables hold only the compounds that appear in our trials.
*/

create schema if not exists reference;
create schema if not exists master;

-- compound_key: parent ChEMBL ID ('CHEMBL3353410'), 'WHO:<inn>' or 'CODE:<code>'
create table reference.compound (
    compound_key   text primary key,
    source         text not null,
    canonical_name text not null,
    inn            text,
    chembl_id      text,
    molecule_type  text,
    max_phase      numeric
);

create table reference.compound_synonym (
    compound_key text not null references reference.compound(compound_key),
    synonym      text not null,
    synonym_key  text not null,
    syn_type     text not null,
    primary key (compound_key, synonym, syn_type)
);

create index on reference.compound_synonym (synonym_key);

create table master.compound (
    compound_id    bigint generated always as identity primary key,
    compound_key   text not null unique,
    canonical_name text not null,
    inn            text,
    chembl_id      text,
    molecule_type  text,
    max_phase      numeric,
    source         text not null
);

-- One raw intervention string can map to several compounds (combinations)
create table master.compound_xwalk (
    raw_name     text not null,
    compound_id  bigint not null references master.compound(compound_id),
    match_method text not null,
    matched_text text,
    score        numeric,
    reviewed     boolean not null default false,
    primary key (raw_name, compound_id)
);
