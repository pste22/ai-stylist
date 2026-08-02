# Feature spec: Virtual Try-On (real, powered by Gemini)

**For an autonomous coding agent.** You cannot ask questions — every decision
is made below. Build exactly this, make the committed test pass, and open a PR.

## Context

- This is Mira, an AI personal stylist: React frontend (`web/`) + Python
  WebSocket backend (`prototype/live_server.py`, run via `watchfiles`).
- The **shopping cart is already fully built** (`web/src/useCart.js`,
  `web/src/CartPanel.jsx`) — DO NOT rebuild it. Only add a "Try on" entry point.
- **Try-on today is a placeholder.** `web/src/TryOnModal.jsx` shows a "Coming
  Soon" silhouette. Your job is to make it real.
- The installed Google GenAI SDK supports virtual try-on via
  `client.models.recontext_image(model=..., source=RecontextImageSource(
  person_image=..., product_images=[...], prompt=...))`. This places a garment
  (product image) onto a person (user photo). Use it.

## Goal

A user picks a product, uploads a photo of themselves, and Mira returns an
AI-generated image of that product worn by them — shown in `TryOnModal`.

## MUST NOT touch

- Auth, payments, the cart hook/panel internals, the greeting logic, the
  filter-chip / `browseCategory` / `category_browse` / `show_more` code paths,
  or `outfit_assembled`. Those were just fixed. Leave them alone.
- Do not change existing WebSocket message shapes; only ADD new ones.
- Do not commit secrets. `prototype/.env` is gitignored — keep it that way.

---

## Part 1 — Backend pure module `prototype/tryon.py` (TEST-GATED)

Create `prototype/tryon.py` with a pure, dependency-free function:

```python
def build_tryon_request(product, user_image_b64, user_mime="image/jpeg"):
    """Validate inputs and assemble the data needed for a Gemini virtual
    try-on (recontext_image) call. Pure function — no network, no SDK imports.
    Raises ValueError on invalid input."""
```

**Exact contract (pinned by `prototype/test_tryon.py` — do not weaken it):**

- Returns a `dict` with keys: `product_id`, `product_name`,
  `product_image_url`, `user_image_b64`, `user_mime`, `prompt`.
- `prompt` is a non-empty instruction string that **contains the product name**
  (e.g. `"Place the {name} on the person in the photo, keeping their face, pose
  and body proportions realistic."`).
- Raises `ValueError` if: `product` is `None`/not a dict; `product` has no
  non-empty `image_url`; `user_image_b64` is empty/`None`; `user_mime` is not
  one of `image/jpeg`, `image/png`, `image/webp` (default `image/jpeg`).

**This module must NOT import `google.genai`** — keep it importable with only
the standard library so the test runs without app dependencies.

## Part 2 — Backend WebSocket wiring in `prototype/live_server.py`

In the message loop (`pump_mic`, alongside `visual_outfit` / `outfit_url` /
`outfit_assembled` handlers), add a handler for a new inbound message:

```json
{ "type": "try_on", "product_id": "...", "image": "<base64>", "mime": "image/jpeg" }
```

Handler behaviour:
1. Look up the product in `_BY_ID` (already defined in the module).
2. Call `tryon.build_tryon_request(product, image, mime)`; on `ValueError`, send
   `{ "type": "try_on_error", "product_id": ..., "message": "<reason>" }`.
3. Call Gemini in a thread (`await asyncio.to_thread(...)`) using the module
   `client` and `types` already imported in the file:
   `client.models.recontext_image(model="<an image-capable Gemini model>",
   source=types.RecontextImageSource(person_image=<user photo as types.Image>,
   product_images=[types.ProductImage(product_image=<product as types.Image>)],
   prompt=<from build_tryon_request>))`. Fetch the product image bytes from
   `product_image_url` with the existing HTTP approach used elsewhere in the
   file; decode the user photo from base64.
4. On success send `{ "type": "try_on_result", "product_id": ...,
   "image": "<base64 of generated image>", "mime": "image/png" }`.
5. On any exception, log it and send `try_on_error` with a friendly message.
   Never crash the session.

Mirror the async/error style of the existing `_outfit_anatomy` handler.

## Part 3 — Frontend

**`web/src/useMiraVoice.js`:**
- Add `sendTryOn(productId, imageBase64, mime = "image/jpeg")` that sends the
  `try_on` message over the open WebSocket (guard on `readyState === OPEN`).
- Handle `try_on_result` and `try_on_error` in `ws.onmessage`. Expose new state:
  `tryOnResult` (`{ productId, image, mime }` or null), `tryOnLoading` (bool),
  `tryOnError` (string or null), plus a `clearTryOn()` setter. Set
  `tryOnLoading` true when `sendTryOn` fires; clear it on result/error; add a
  ~45s safety timeout like `sendOutfitImage`.

**`web/src/TryOnModal.jsx`:**
- Replace the "Coming Soon" placeholder with a working flow:
  1. A file input to upload the user's photo (`accept="image/*"`; read as
     base64 like the outfit uploader in `App.jsx`'s `TextInputRow`).
  2. On upload, call the passed-in `onTryOn(productId, base64, mime)`.
  3. Show a loading state while `loading`, the returned image when `result`
     is present, and a friendly error when `error`. Keep the existing silhouette
     as the empty/pre-upload state.
- Props: `product`, `onClose`, `onTryOn`, `result`, `loading`, `error`.

**`web/src/App.jsx`:**
- Wire `sendTryOn`, `tryOnResult`, `tryOnLoading`, `tryOnError`, `clearTryOn`
  from `useMiraVoice` into a rendered `<TryOnModal>` controlled by a
  `tryOnProduct` state.
- Add a **"Try on" button** to product cards (in `ProductCard.jsx`, a new
  optional `onTryOn` prop + button) and to cart items in `CartPanel.jsx`.
  Clicking sets `tryOnProduct` and opens the modal. Requires an active session
  (`connected`); if not connected, start one first (reuse existing patterns).
- Keep styling consistent with existing cards/modals (`styles.css`). Add minimal
  CSS as needed; do not restyle unrelated components.

---

## Verification (HARD GATE — must pass)

From the `prototype/` directory:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest test_tryon.py -v
```

**All tests in `prototype/test_tryon.py` must pass.** Do not modify the test.

Also confirm both builds are clean:
```bash
cd web && npm install && npm run build      # must succeed
cd prototype && python -c "import ast; ast.parse(open('live_server.py').read())"
```

## Acceptance criteria

- [ ] `prototype/tryon.py` exists; `test_tryon.py` passes unmodified.
- [ ] `live_server.py` handles `try_on` → `try_on_result` / `try_on_error`,
      never crashes the session, uses `recontext_image`.
- [ ] `TryOnModal` supports photo upload → shows AI-generated try-on image, with
      loading + error states.
- [ ] "Try on" entry points on product cards and cart items open the modal.
- [ ] `npm run build` succeeds; `live_server.py` parses.
- [ ] No changes to auth, payments, cart internals, greeting, or the
      filter/show_more/outfit_assembled code paths.

## Non-interactive decisions (already made — do not second-guess)

- Use Gemini `recontext_image` for generation (not a third-party try-on API).
- Result image returned as base64 PNG over the existing WebSocket (no new REST).
- Photo is processed in-memory only; do NOT persist user photos anywhere.
- If `recontext_image` needs a specific model id and you're unsure, pick a
  current image-capable Gemini model and leave a clear `# TODO: confirm model`
  comment — do not block on it.
