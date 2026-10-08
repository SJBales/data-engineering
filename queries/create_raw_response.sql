/* 
Creates:
  1. Raw schema if it does not exist
  2. Raw response table if it does not exist
*/

create schema if not exists raw;

create table raw.raw_responses(
    nct_id       text        not null,
    raw_json     jsonb       not null,
    fetched_at   timestamptz not null,
    params       jsonb       not null,
    response_url text        not null,
    primary key (nct_id, fetched_at)
);