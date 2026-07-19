# AGENTS.md

## Cursor Cloud specific instructions

This is a single-product monorepo — **Mira**, a voice-first AI stylist — with two
independently-run halves plus CLI tooling:

- `web/` — Vite + React frontend (dev server on port `5173`). Scripts in `web/package.json`.
- `prototype/` — Python voice bridge `live_server.py` (WebSocket on port `8765`, relays to Gemini Live) plus the stylist brain, catalog, and CLI (`text_loop.py`). Deps in `prototype/requirements.txt`.

Python deps live in a repo-root virtualenv at `.venv/` (created by the update script). Web deps are in `web/node_modules/`.

### Running the services (dev)
- Start both together with `./dev.sh`, **but** `dev.sh` invokes bare `python`, which is NOT the venv. Either activate the venv first (`source .venv/bin/activate`) or run the bridge directly with `.venv/bin/python prototype/live_server.py`. Otherwise the bridge can't find its dependencies.
- Frontend: `cd web && npm run dev` (serves `http://localhost:5173`; also proxies `/mira-ws` → the bridge on `:8765`, see `web/vite.config.js`).

### Non-obvious gotchas
- The voice bridge **boots without `GEMINI_API_KEY`** (the HTTP health check at `/` returns `OK`), but the moment a browser opens a voice session it raises `RuntimeError: GEMINI_API_KEY missing` and closes the WebSocket with code `1011`. Put `GEMINI_API_KEY` in `prototype/.env` (copy `prototype/.env.example`) for actual voice chat.
- The web app is fully **gated behind Supabase OAuth login** (`web/src/App.jsx` returns the login screen when `!user`). It needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `web/.env` (gitignored), plus a Supabase project with OAuth providers (Google/Facebook/GitHub) configured. `@supabase/supabase-js` `createClient` throws if these are empty, so at minimum non-empty placeholder values are required just to render the login screen; real values + a configured provider are required to sign in and reach the chat.
- Product catalog: `PRODUCT_SOURCE` defaults to `local` (bundled offline `prototype/data/products.json`), so no database is needed for the catalog. Supabase is only required for auth, chat history, and the `supabase` catalog source.
- Tests: `cd prototype && ../.venv/bin/python -m pytest -q`. Note `test_product_source.py::test_get_source_curated_falls_back_when_unseeded` currently **fails on `main`** because `prototype/data/affiliate_products.json` now ships real seeded products (the test assumes an unseeded template file) — this is a pre-existing test/data drift, not an environment problem.
- Lint: none configured (no ESLint/Prettier/pre-commit).
