create schema if not exists master;

create table master.sponsor (
    sponsor_id bigint generated always as identity primary key,
    canonical_name text not null,
    class text
);

create table master.sponsor_xwalk (
    raw_name text primary key,
    sponsor_id    bigint not null references master.sponsor(sponsor_id),
    match_method  text not null,
    score         numeric,
    reviewed      boolean default false
);