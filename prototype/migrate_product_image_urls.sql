-- Gallery images for Amazon (and other) products.
-- Run in Supabase → SQL Editor → New query → Run
alter table products
  add column if not exists image_urls jsonb not null default '[]'::jsonb;

-- Backfill primary from image_url where gallery is empty
update products
set image_urls = jsonb_build_array(image_url)
where (image_urls is null or image_urls = '[]'::jsonb)
  and image_url is not null
  and image_url <> '';
