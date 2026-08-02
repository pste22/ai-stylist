"""
One-time script: generate text embeddings for all active products using
Google's text-embedding-004 model and store them in Supabase (products.embedding).

Usage:
  SUPABASE_URL=... SUPABASE_SECRET_KEY=... GEMINI_API_KEY=... python generate_embeddings.py

Prerequisites:
  1. Run migrate_vector_search.sql in Supabase SQL Editor first.
  2. pip install google-genai (already in requirements.txt)
"""

import os
import time
import sys
import product_store as ps

try:
    from google import genai as _genai
except ImportError:
    print("ERROR: pip install google-genai")
    sys.exit(1)

_EMBED_MODEL  = "gemini-embedding-001"
_EMBED_DIMS   = 768   # truncated via output_dimensionality (ivfflat max = 2000)
_BATCH_SIZE   = 20    # Gemini embedding API batch limit
_SLEEP_S     = 0.5  # polite rate limiting between batches


def _make_text(p: dict) -> str:
    """Compact product description for embedding."""
    parts = [p.get("name", ""), p.get("category", ""), p.get("color", "")]
    styles = p.get("style") or []
    if isinstance(styles, list):
        parts.extend(styles)
    return " | ".join(x for x in parts if x).strip()


def main():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = _genai.Client(api_key=api_key)
    db     = ps._db()

    # Load all active products that don't yet have embeddings
    print("Loading products without embeddings…")
    result = (
        db.table("products")
          .select("id,name,category,color,style,price")
          .eq("is_active", True)
          .is_("embedding", "null")
          .execute()
    )
    products = result.data or []
    print(f"  {len(products)} products need embeddings")

    if not products:
        print("All products already have embeddings. Done.")
        return

    total    = len(products)
    done     = 0
    errors   = 0

    for i in range(0, total, _BATCH_SIZE):
        batch = products[i : i + _BATCH_SIZE]
        texts = [_make_text(p) for p in batch]

        try:
            resp = client.models.embed_content(
                model=_EMBED_MODEL,
                contents=texts,
                config={"output_dimensionality": _EMBED_DIMS},
            )
            embeddings = [e.values for e in resp.embeddings]
        except Exception as e:
            print(f"  ✗ batch {i}–{i+len(batch)}: {e}")
            errors += len(batch)
            time.sleep(2)
            continue

        # Upsert embeddings back to Supabase
        for p, emb in zip(batch, embeddings):
            try:
                db.table("products").update({"embedding": emb}).eq("id", p["id"]).execute()
                done += 1
            except Exception as e:
                print(f"  ✗ upsert {p['id']}: {e}")
                errors += 1

        pct = done / total * 100
        print(f"  {done}/{total} ({pct:.0f}%) — batch done", end="\r")
        time.sleep(_SLEEP_S)

    print(f"\nDone. {done} embeddings saved, {errors} errors.")


if __name__ == "__main__":
    main()
