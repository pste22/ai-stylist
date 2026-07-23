-- VCommission integration schema additions
-- Run once in Supabase SQL editor

-- Currency field (default USD for existing products; INR for VCommission imports)
ALTER TABLE products ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'USD';

-- VCommission advertiser slug (myntra | ajio | nykaa_fashion | amazon_india)
ALTER TABLE products ADD COLUMN IF NOT EXISTS vc_advertiser text;

-- VCommission SKU for deduplication
ALTER TABLE products ADD COLUMN IF NOT EXISTS vc_sku text;

-- Index for fast advertiser-scoped queries (used by mark_inactive)
CREATE INDEX IF NOT EXISTS idx_products_vc_advertiser ON products (vc_advertiser) WHERE vc_advertiser IS NOT NULL;

-- Update existing Amazon products to USD currency (already correct, just explicit)
UPDATE products SET currency = 'USD' WHERE source LIKE 'amazon%' AND currency IS NULL;
