-- Faceted browse fields for Zara-style filters.
-- Run in Supabase → SQL Editor (safe to re-run).

alter table products add column if not exists brand text;
alter table products add column if not exists facets jsonb not null default '{}'::jsonb;

create index if not exists idx_products_brand
  on products (brand)
  where is_active = true and brand is not null;

create index if not exists idx_products_facets_gin
  on products using gin (facets jsonb_path_ops);

comment on column products.brand is 'Normalized brand for fast filter chips';
comment on column products.facets is 'Derived filter labels: colour, material, fit, size[], occasion[], new_in, …';
