# ShopSense — Decision Log

> Every significant architectural and product choice, written during the build.
> Format: **Decision** → Considered → Chose → Because

---

## Product Decisions

---

### D-01: One recommendation, not three

**Considered:** Show top 3 products like most shopping tools  
**Chose:** Show exactly one recommendation  
**Because:** Showing 3 recreates the decision paralysis we're trying to solve. If a user wanted 3 options, they wouldn't need an AI agent — they'd use a search engine. The value proposition is a committed, explained answer. One forces the agent to be accountable.

**Tradeoff:** If the recommendation is wrong, the user must rephrase. We accept this — the elimination panel and regret scenario give them enough signal to push back intelligently.

---

### D-02: Confidence score as primary UI metaphor

**Considered:** Hide the internal scoring, just show the recommendation  
**Chose:** Surface the confidence score as an animated ring that fills in real time  
**Because:** It externalises the agent's state — the user can see why they're being asked a follow-up question (score too low) and when the agent is ready to commit (ring turns green at 80%). It also builds trust: the agent isn't a black box.

**Secondary benefit:** The score breakdown (category/budget/use-case bars) teaches users what information helps the agent. Users learn to give better inputs.

---

### D-03: Max 2 follow-up questions

**Considered:** Keep asking until confidence hits 80%  
**Chose:** Hard cap at 2 follow-up questions, then commit regardless  
**Because:** Asking 5+ questions before giving a recommendation is a worse user experience than a slightly lower-confidence answer. Two questions covers budget and use case — the two highest-signal gaps. After that, commit and show your reasoning.

---

### D-04: Regret risk framing over pros/cons

**Considered:** List pros and cons of the recommended product  
**Chose:** Show a personalised "you'll regret this if…" scenario + honest tradeoff  
**Because:** Pros/cons are generic and detached from the user's stated needs. "You'll regret this if you plan to run trails — this is road-only" is specific to what the user actually said. It's more useful and more trustworthy.

---

### D-05: Elimination panel with AI reasons

**Considered:** Only show the winning product  
**Chose:** Show all other considered products with one-sentence elimination reasons  
**Because:** Users trust a recommendation more when they can see what was rejected and why. "Over budget — ₹89,999 exceeds your ₹80K limit" is verifiable. "Lower match score" is not. Transparency is the feature.

---

## Architecture Decisions

---

### D-06: Shopify Admin API over Storefront API

**Considered:** Shopify Storefront API (public-facing, Storefront token)  
**Chose:** Shopify Admin API (shpat_ token, Admin GraphQL)  
**Because:** Admin API gives richer filtering (vendor:, tag:, product_type:), access to all products, and metafields support. The Storefront API is for customer-facing storefronts; the Admin API is for integrations. We're an integration.

---

### D-07: Shopify as primary, browser agent as fallback

**Considered:** Browser agent as sole source (live scraping only)  
**Chose:** Shopify store first, browser agent only when Shopify returns nothing  
**Because:** Browser scraping is slow (20–60s), unreliable (sites block headless browsers), and non-deterministic. A Shopify store is instant, structured, and always available. For the hackathon demo, reliability matters more than live-data purity.

**Tradeoff:** Shopify store is curated, not exhaustive. A user searching for an obscure product may fall through to the browser agent.

---

### D-08: Deterministic confidence score (zero LLM)

**Considered:** Ask the LLM to rate how confident it is in a recommendation  
**Chose:** Pure math formula: category/budget/use-case/priority match + penalties  
**Because:** LLM confidence self-reports are unreliable and non-auditable. The deterministic formula is transparent — you can see exactly which component contributed what. It's also instant (no API call) and consistent across runs.

**Key insight:** The score doesn't need to be "correct" — it needs to be a consistent signal for when to ask follow-ups and when to commit. Math is better than vibes for this.

---

### D-09: Server-Sent Events over WebSockets

**Considered:** WebSockets for full-duplex real-time communication  
**Chose:** SSE (one-directional streaming over standard HTTP)  
**Because:** We only need server-to-client streaming. WebSockets add complexity (connection management, reconnection logic) for no benefit in this flow. SSE works over standard HTTP, is supported by all modern browsers, and integrates cleanly with FastAPI's StreamingResponse.

---

### D-10: Groq over OpenAI

**Considered:** OpenAI GPT-4o for LLM calls  
**Chose:** Groq llama-3.3-70b-versatile  
**Because:** Free tier with no credit card. Same OpenAI-compatible API interface (zero code changes to switch). Groq's inference speed is faster than OpenAI for streaming use cases. For a hackathon where we can't guarantee a billing account, free is a hard requirement.

**Vision model:** meta-llama/llama-4-scout-17b-16e-instruct (the previous llama-3.2-90b-vision-preview was decommissioned during development — caught from Railway logs and switched immediately).

---

### D-11: Multi-turn session intent merging

**Considered:** Treat each message as independent, start intent fresh each time  
**Chose:** Merge each new intent into the session's accumulated intent  
**Because:** Users give context across multiple messages — budget in message 1, use case in message 2, brand constraint in message 3. Starting fresh each time would require re-stating everything.

**Implementation detail:** New non-empty values override old. missing_info fields are re-checked after merge and removed if now answered — otherwise the ambiguity penalty would persist even after a follow-up answer.

---

### D-12: Tech synonym expansion in confidence engine

**Considered:** Pure keyword matching ("GPU" → look for "GPU" in product text)  
**Chose:** Synonym dictionary: "GPU" → ["nvidia", "rtx", "gtx", "radeon", "graphics card"]  
**Because:** Product descriptions rarely use the exact word the user used. Without expansion, priority scores are systematically underestimated for technical categories. A user asking for "GPU" should correctly score a product described as "NVIDIA RTX 4070".

---

### D-13: Parallel vision extraction

**Considered:** Sequential — visit each page, extract, move to next  
**Chose:** Parallel — asyncio.gather() on all vision calls simultaneously  
**Because:** Sequential vision calls on 3 pages would take 3× the time. Wall-clock time goes from ~45s sequential to ~15s parallel.

---

### D-14: Google-first link discovery (browser agent)

**Considered:** Hardcoded URL templates for each site (Amazon search URL, Flipkart search URL)  
**Chose:** Open Google with a natural-language query, extract organic result URLs from DOM  
**Because:** Google already knows which product listing on which site best matches a query. Hardcoded search URLs produce generic category pages; Google produces specific product listing pages. The quality of the landing page dramatically affects vision extraction quality.

---

### D-15: Brand hard filter (three-layer)

**Considered:** Trust the LLM to only recommend the right brand  
**Chose:** Three-layer brand enforcement: (1) intent prompt, (2) keyword fallback, (3) post-extraction hard filter  
**Because:** During testing, BMW queries returned Hyundai and Maruti results because the visited page showed all cars. The LLM extracted all visible products. Only a hard Python-level filter reliably removes wrong-brand products regardless of what the vision model extracted.

---

### D-16: Railway over Render for backend

**Considered:** Render (free tier)  
**Chose:** Railway  
**Because:** Render's free tier has 512MB RAM — not enough for Playwright + Chromium + Python simultaneously. Railway has sufficient memory, better environment variable management, and faster cold starts.

---

## Frontend Decisions

---

### D-17: Framer Motion for confidence ring

**Considered:** CSS animation only  
**Chose:** Framer Motion with spring physics  
**Because:** The confidence ring needs to animate smoothly to arbitrary values (0→72→84→91) as the conversation progresses. CSS transitions require knowing the target value upfront. Framer Motion handles dynamic values naturally.

---

### D-18: Web Speech API for voice input

**Considered:** Whisper API, AssemblyAI, Google Speech-to-Text  
**Chose:** Browser Web Speech API  
**Because:** Zero cost, zero API key, zero latency. Works natively in Chrome and Edge. The en-IN locale handles Indian accents. Voice is a nice-to-have — we didn't want to add billing complexity for it.

---

### D-19: Token streaming into recommendation card

**Considered:** Stream reasoning into a separate chat bubble after the product card  
**Chose:** Stream reasoning tokens directly into the product card's reasoning section in real-time  
**Because:** The card appears immediately with all product data, and you watch the reasoning build inside it. The card is never re-mounted — only the reasoning string grows via a splice into React state. This feels like the agent thinking out loud, not delivering a report.

---

### D-20: DuckDuckGo over Google Custom Search for product images

**Considered:** Google Custom Search API (100 free queries/day), Bing Image Search API, Playwright scraping Amazon/Flipkart  
**Chose:** DuckDuckGo via the `ddgs` library  
**Because:** Google's 100/day quota blocks a full 199-product run in one shot. Playwright scraping was completely blocked by bot detection (0/201 success rate). DuckDuckGo has no API key, no daily quota, and returns usable image results with proper filtering.

**Key implementation detail:** Creating a new `DDGS()` instance per query instantly triggers rate limits (403). A single shared session across all queries + a 10-second inter-query delay keeps DDG happy.

**Word-boundary bug caught mid-run:** `"car" in "skincare"` is True in Python — all skincare products were being sent to the car image query path (returning Audi photos). Fixed with `re.search(r'\bcar\b', product_type)`. 22 bad images were deleted and re-uploaded correctly.

**Cascade fallback:** Shopify returns 422 when it can't fetch a URL (CDN hotlink protection — e.g., assets.bose.com). Script now tries up to 10 ranked DDG candidates per product before marking a failure. Final result: 199/199 products imaged, 0 failures.

---

*Last updated: May 2026*
