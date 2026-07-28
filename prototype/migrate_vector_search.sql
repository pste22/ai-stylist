-- ── Vector search migration ───────────────────────────────────────────────────
-- Run this in Supabase SQL editor (Dashboard → SQL Editor → New query)
--
-- Step 1: Enable pgvector extension
create extension if not exists vector;

-- Step 2: Add embedding column
-- gemini-embedding-001 truncated to 768 dims (ivfflat max = 2000)
alter table products drop column if exists embedding;
alter table products add column embedding vector(768);

-- Step 3: Index for fast ANN search
create index if not exists products_embedding_idx
  on products
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 50);

-- Step 4: Similarity search RPC
create or replace function match_products(
  query_embedding  vector(768),
  match_count      int     default 5,
  filter_category  text    default null,
  min_price        numeric default null,
  max_price        numeric default null
)
returns table (
  id            text,
  name          text,
  category      text,
  color         text,
  price         numeric,
  image_url     text,
  affiliate_url text,
  similarity    float
)
language sql stable
as $$
  select
    id::text, name, category, color, price, image_url, affiliate_url,
    1 - (embedding <=> query_embedding) as similarity
  from products
  where is_active = true
    and embedding is not null
    and (filter_category is null or category = filter_category)
    and (min_price is null or price >= min_price)
    and (max_price is null or price <= max_price)
  order by embedding <=> query_embedding
  limit match_count;
$$;
