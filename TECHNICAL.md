# ShopSense — Technical Document

**Hackathon:** Kasparro Agentic Commerce — Track 1 — April 2026

---

## 1. System Overview

ShopSense is a full-stack AI shopping agent with two deployed services:

- **Frontend:** Next.js 15 on Vercel — chat interface, animated confidence meter, SSE consumer
- **Backend:** FastAPI on Railway — intent extraction, product search, confidence scoring, LLM streaming

Communication is via **Server-Sent Events (SSE)** — a single long-lived HTTP response that streams structured JSON events as they are produced. This enables live status updates ("Searching store…"), token-by-token reasoning, and a progressive UI that feels fast even when the backend is doing work.

---

## 2. Request Lifecycle

```
POST /api/chat  {message, session_id, history}
        │
        ├─ 1. extract_intent()          Groq LLM → structured JSON
        │      merge with session intent (multi-turn)
        │
        ├─ 2. compute_confidence()      Deterministic math, zero LLM
        │      yields: confidence SSE event → frontend
        │
        ├─ 3. generate_followup()?      Only if score < 80 AND followup_count < 2
        │      Groq LLM → targeted question
        │      yields: followup SSE event → return early
        │
        ├─ 4a. shopify_client.search()  Admin GraphQL → instant product list
        │      OR
        │   4b. browser_agent.stream()  Playwright → Google → vision → products
        │      yields: status SSE events during search
        │
        ├─ 5. compute_confidence()      Re-score with actual products
        │      yields: confidence SSE event
        │
        ├─ 6. rank_and_reason()         Score + sort + stream reasoning
        │      yields: recommendation_start, token×N, recommendation_done
        │
        └─ done SSE event
```

---

## 3. Intent Extraction

**File:** `backend/agent/intent_extractor.py`

Uses Groq `llama-3.3-70b-versatile` via the OpenAI-compatible endpoint. The prompt returns a JSON object with:

```json
{
  "category": "running shoes",
  "use_case": "road running",
  "budget_max": 5000,
  "priorities": ["cushioning", "flat feet support"],
  "constraints": ["brand: Nike"],
  "missing_info": []
}
```

**Multi-turn merge:** Each new intent is merged with the session's existing intent — new non-empty values override, old values persist. This means a follow-up answer ("oily skin") merges into a prior intent that already has `budget_max: 500` without losing it.

**Missing info cleanup:** After merging, fields listed in `missing_info` are re-checked — if they've been answered, they're removed. This prevents the ambiguity penalty persisting after follow-up answers.

**Keyword fallback:** If the LLM call fails or times out, a regex-based fallback extracts budget (₹/Rs patterns), brand names, and use-case keywords. This ensures zero dead-ends.

**Brand constraint extraction:** Brands like "Nike", "Samsung", "BMW" are extracted into `constraints` as `"brand: Nike"`. This feeds both the Shopify `vendor:` filter and the post-extraction brand filter in the browser agent.

---

## 4. Confidence Engine

**File:** `backend/agent/confidence_engine.py`

100% deterministic — no LLM calls. Scores 0–100 across 6 components:

```
Category match (0–25):   fraction of products whose text contains category keywords
Budget match (0–20):     fraction of products within budget_max
Use case match (0–25):   fraction of products whose text matches use_case words
Priority match (0–15):   per-priority proportional — 2 of 3 priorities matched → 10/15
Rating bonus (0–5):      average rating quality across products (4.5★ + 1000 reviews → 5)
Penalty (−8 per gap):    each unresolved missing_info item
Constraint penalty (−15):per constraint that no product meets
```

**Tech synonym expansion:** The engine maintains a `_SYNONYMS` dictionary that maps user terms to product terms:
- `"GPU"` → `["nvidia", "rtx", "gtx", "radeon", "graphics card", "dedicated"]`
- `"battery life"` → `["battery", "mah", "5000mah", "all day"]`
- `"screen quality"` → `["oled", "amoled", "ips", "4k", "144hz", "1080p"]`

This means a user asking for "GPU" correctly scores a product described as "NVIDIA RTX 4070" without requiring the word "GPU" to appear.

**Commit threshold:** ≥ 80 points. Below this, the agent asks a follow-up (max 2 times).

---

## 5. Shopify Integration

**File:** `backend/agent/shopify_client.py`

Primary product source. Uses the **Shopify Admin GraphQL API** (not Storefront):
- Endpoint: `https://{store}/admin/api/2025-01/graphql.json`
- Header: `X-Shopify-Access-Token: shpat_...`
- Requires `read_products` scope

**Query building:**
```python
# "running shoes for road running, brand: Nike"
# → status:ACTIVE (title:*running* OR tag:running OR tag:road) vendor:"Nike"
```

Category and use-case words generate `title:*word* OR tag:word` OR expressions. Brand constraints become a hard AND `vendor:"Brand"` clause.

**Metafields:** Each product carries `shopsense.rating` (number_decimal), `shopsense.review_count` (number_integer), and `shopsense.review_highlight` (single_line_text_field). These are queried via:
```graphql
metafields(first: 10, namespace: "shopsense") { edges { node { key value } } }
```

**Product URL:** `onlineStoreUrl` returns the live product page URL. When absent, a slug is derived from the title.

**Fallback:** If `SHOPIFY_STORE_URL` or `SHOPIFY_ADMIN_TOKEN` are absent, `is_configured()` returns False and the browser agent fires instead.

---

## 6. Browser Agent (Fallback)

**File:** `backend/agent/browser_agent.py`

Fires only when Shopify returns no results or is unconfigured. Uses Playwright (headless Chromium) + Groq Vision.

**Pipeline:**
1. `_build_google_query(intent)` → natural language query e.g. `"Nike running shoes road India"`
2. `_google_search_links()` → opens Google, evaluates DOM JS to extract top organic URLs, prefers known shopping domains (Amazon, Flipkart, CarWale, OLX, Cars24, Spinny)
3. Top 3 links visited in **parallel** via `asyncio.gather` + `asyncio.create_task`
4. Each page: 2 scroll positions, screenshots captured as base64
5. All screenshots sent to Groq Vision **simultaneously** (parallel, not sequential)
6. JSON product arrays merged, `_sanity_filter` applied (price > 0, title non-empty)
7. `_brand_filter` hard-removes wrong-brand products
8. Budget filter applied

**Hard timeout:** 60 seconds total via `asyncio.get_event_loop().time()`. If exceeded, whatever products have been extracted so far are returned.

**Vision model:** `meta-llama/llama-4-scout-17b-16e-instruct` (Groq). Each screenshot yields a JSON array of products with title, price, rating, review_count, review_highlight, url, tags.

**Product URL strategy:** `page_url` (the URL actually visited, already a specific listing thanks to Google) if non-generic (not `/`, `/search`, `/s`, short paths). Falls back to `_title_search_url()` which builds `site.com/search?q=Product+Title`.

---

## 7. Product Ranker

**File:** `backend/agent/product_ranker.py`

**Constraint pre-filter:** Before scoring, products that hard-violate explicit constraints (brand mismatch, fuel type, seating capacity) are removed. If all products are filtered, falls back to full list.

**Scoring:** Each product is passed individually to `compute_confidence(intent, [product])`. Products sorted descending by score. Top product is the recommendation.

**Reasoning stream:** Groq `llama-3.3-70b-versatile` with `stream=True`. Tokens yielded as `{"type": "token", "text": "..."}` SSE events. Frontend appends each token to the recommendation card in real time.

**Elimination reasons:** Single batched LLM call for all non-top products. Returns JSON array of `{title, reason}`. Falls back to deterministic reasons (over budget, use-case mismatch, lower rating) if LLM fails.

**Regret assessment:** Separate non-streaming Groq call returns `{regret_risk: low|medium|high, regret_scenario: "...", tradeoff: "..."}`. Sent as `recommendation_done` event after reasoning stream completes.

---

## 8. Frontend SSE Architecture

**File:** `frontend/lib/api.ts`

`streamChat()` is an async generator that yields typed `SSEEvent` objects. The ChatInterface consumes these with `for await (const event of streamChat(...))` and dispatches to React state setters by event type.

**Streaming recommendation:** The `recommendation_start` event creates the product card with empty reasoning. Subsequent `token` events append to the last recommendation's reasoning string in-place. `recommendation_done` patches in regret_risk and tradeoff. The card is never re-mounted — only its reasoning string grows.

**Session state:** A UUID session ID is generated client-side on mount. It's sent with every request and echoed back in the first confidence event. The backend uses it to look up the in-memory session store `{followup_count, intent}`.

---

## 9. Failure Handling

| Failure | Handling |
|---|---|
| Groq LLM timeout / error | Keyword regex fallback for intent; deterministic elimination reasons |
| Shopify API error / empty results | Falls back to browser agent |
| Browser agent timeout (> 60s) | Returns whatever products extracted so far |
| Google blocks Playwright | `_google_search_links()` returns empty; each product site queried directly |
| Vision LLM returns invalid JSON | `re.search(r'\[.*\]', raw, re.DOTALL)` extracts best-effort array |
| Image CDN blocks hotlinking | `onError` on Next.js Image → TrendingUp icon placeholder |
| All search paths return nothing | SSE `message` event: "I couldn't find matching products…" — no crash |
| Frontend fetch fails | Catch block → "I had trouble connecting" — never a silent failure |

---

## 10. Deployment

| Service | Platform | Config |
|---|---|---|
| Frontend | Vercel | Root: `frontend/`, env: `NEXT_PUBLIC_API_URL` |
| Backend | Railway | Root: `backend/`, start: `uvicorn main:app --host 0.0.0.0 --port $PORT` |

**Railway build:** `pip install -r requirements.txt && playwright install chromium && playwright install-deps`

**Windows dev:** `start.py` sets `asyncio.WindowsProactorEventLoopPolicy()` before importing FastAPI. Required because Playwright's Chromium process spawning needs ProactorEventLoop — SelectorEventLoop (the default on Windows) cannot spawn subprocesses.

**CORS:** Configured via `ALLOWED_ORIGINS` env var (comma-separated). Set to Vercel frontend URL in production.

---

## 11. Store Data Pipeline

**Scripts in `backend/scripts/`** — run once to set up the store:

| Script | Purpose |
|---|---|
| `populate_shopify.py` | Creates 199 products with INR pricing, tags, and `shopsense.*` metafields |
| `fix_product_names.py` | Strips auto-generated tier suffixes (Value/Plus/Pro/Elite/Ultra) from 140 products; deletes 2 duplicates |
| `upload_images_ddg.py` | Searches DuckDuckGo Images for each product by name, scores results (prefers brand CDNs + large images), uploads to Shopify. Cascades through up to 10 candidates if Shopify rejects a URL (hotlink protection). No API key required. |
| `upload_images_google.py` | Google Custom Search API fallback — higher quality but 100 queries/day free limit |
| `remove_bad_images.py` | Deletes images matching a filename pattern (used to clean up 22 wrong images uploaded to skincare products due to a word-boundary bug: `"car" in "skincare"`) |
| `list_products.py` | Paginated product audit — prints ID, vendor, product_type, title |

**Image pipeline design decisions:**
- Single shared `DDGS()` session across all queries — avoids per-query bot detection that triggers 403 rate limits
- 10-second inter-query delay to stay within DDG's rate window
- Word-boundary regex (`\bcar\b`) for product type matching — prevents "Skincare" matching the car query path
- Cascade fallback: Shopify 422 (hotlink rejection) → try next candidate URL from ranked DDG results

---

## 12. Limitations

- **Railway cold starts:** If the backend sleeps, first request takes ~15s to wake. Hit `/health` before a live demo
- **Browser agent rate limits:** Google may throttle headless browsers. Retry logic is not implemented — the 60s timeout fires instead
- **Playwright on Railway:** Requires `playwright install-deps` which adds ~2 min to first deploy
- **In-memory sessions:** Sessions are stored in a Python dict — lost on restart. No persistence layer
- **Single recommendation:** If the top product is genuinely wrong, the user must rephrase rather than paginate

---

## 12. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.111.0 | Async web framework, StreamingResponse for SSE |
| `playwright` | ≥1.40 | Headless Chromium browser automation |
| `httpx` | 0.27.0 | Async HTTP for Shopify Admin API |
| `openai` | ≥1.0 | Groq-compatible client (same interface) |
| `ddgs` | latest | DuckDuckGo image search — no API key, no daily quota |
| `python-dotenv` | 1.0.1 | Env var loading |
| `next` | 15.x | React framework, App Router |
| `framer-motion` | latest | Confidence ring, message animations |
| `tailwindcss` | v4 | Utility CSS |
| `lucide-react` | latest | Icons |
