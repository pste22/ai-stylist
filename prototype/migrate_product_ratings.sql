-- Optional Amazon / retailer ratings for cold-start social proof on Quick View.
-- Safe to re-run. Populate via rainforest/PA-API importers when available.

alter table products add column if not exists rating numeric(3,2);
alter table products add column if not exists ratings_total integer;

comment on column products.rating is 'Retailer average rating 0–5 (e.g. Amazon); shown as cold-start until Mira reviews exist';
comment on column products.ratings_total is 'Retailer rating count';
