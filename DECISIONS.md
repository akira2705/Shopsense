# ShopSense — Decision Log

Every significant architectural decision made during the build, written in real-time (not retroactively). Each entry includes context, the choice made, reasoning, and honest tradeoffs.

---

## [2026-04-24] Monorepo — frontend + backend in one repo

**Context:** Could split into two repos for cleaner separation.  
**Choice:** Single repo with `/frontend` and `/backend` folders.  
**Reasoning:** Simpler for judges to review. One GitHub link in submission. Easier to show the full system at once. Vercel and Render both support subdirectory deploys.  
**Tradeoff:** Slightly messier deploys — each platform needs root directory configured. Acceptable.

---

## [2026-04-24] FastAPI (Python) over Express (Node.js)

**Context:** Both are valid choices. Node.js would match the frontend language.  
**Choice:** FastAPI (Python 3.11).  
**Reasoning:** Team is stronger in Python. FastAPI has first-class async/await support and native streaming via `StreamingResponse`. Pydantic v2 gives us strong request validation for free. The browser automation (Playwright) ecosystem is also stronger in Python.  
**Tradeoff:** Two different runtimes. Backend can't share TypeScript types with frontend directly. We mitigate this with a typed SSE client in `lib/api.ts`.

---

## [2026-04-24] Server-Sent Events (SSE) over WebSockets for streaming

**Context:** Real-time streaming needed for the confidence meter, browser status, and LLM token streaming.  
**Choice:** SSE (Server-Sent Events) via FastAPI `StreamingResponse`.  
**Reasoning:** The communication is one-directional — server pushes, client reads. SSE is simpler to implement, works over standard HTTP/1.1, needs no upgrade handshake, and is natively supported by all browsers. WebSockets are overkill for a request-response + stream pattern.  
**Tradeoff:** Can't receive messages from client during streaming. Acceptable — new user messages start a new request.

---

## [2026-04-24] Groq over OpenAI / Anthropic for LLM

**Context:** OpenAI and Anthropic both offer capable models. This is an Anthropic-adjacent hackathon.  
**Choice:** Groq (`llama-3.3-70b-versatile` for text, `llama-3.2-90b-vision-preview` for vision).  
**Reasoning:** Groq's free tier is genuinely free — no credit card required, generous rate limits, and it's the fastest inference available. The API is OpenAI-compatible, so switching from `openai` to Groq is a one-line base URL change. This also means the demo never fails due to rate limits during judging.  
**Tradeoff:** Llama models are slightly less instruction-following than GPT-4o or Claude Sonnet for structured JSON. We mitigate with robust regex fallback extraction and explicit JSON-only prompts.

---

## [2026-04-24] Playwright browser agent over product APIs (Amazon API, Flipkart API)

**Context:** Could use official product APIs for structured data. Amazon has a Product Advertising API; Flipkart had an affiliate API.  
**Choice:** Playwright (headless Chromium) + Groq Vision to read screenshots.  
**Reasoning:** Amazon's PA-API requires affiliate approval (days of wait time). Flipkart's API is deprecated. OLX and CarWale have no public API. Browser automation gets real, live, publicly visible data from any site — the same data a human user sees. This also means the demo shows genuinely current prices and availability.  
**Tradeoff:** Sites can block headless browsers. We handle this with a realistic user agent, a curated demo fallback pool (35+ Indian products), and graceful degradation with a user-facing status message.

---

## [2026-04-24] Confidence score is deterministic — zero LLM

**Context:** Could ask the LLM "how confident are you in this recommendation?"  
**Choice:** Pure math in `confidence_engine.py`. No LLM.  
**Reasoning:** LLM confidence estimates are unreliable (they hallucinate certainty), non-reproducible (same input, different score), and unexplainable. A deterministic formula is transparent — judges can read it and verify every point. It's also immune to prompt injection and works consistently under any load.  
**Formula:** Category match (25) + Budget match (20) + Use case match (25) + Priority match (15) − Ambiguity penalty (8 per missing field).  
**Tradeoff:** The formula is an approximation of "fit." A perfectly matched product with unusual tags might score lower. We accept this in exchange for full transparency.

---

## [2026-04-24] Confidence threshold of 80 to commit

**Context:** Need a threshold to stop asking questions and start recommending.  
**Choice:** Score ≥ 80 triggers the recommendation without further questions.  
**Reasoning:** Below 80 means meaningful ambiguity that a targeted question can resolve (each missing field costs 8 points). Above 80, we have enough signal. 80 corresponds roughly to: full category + budget + use case with no unresolved gaps.  
**Tradeoff:** Some borderline cases (score 78) might benefit from one more question. We accept this to avoid over-asking.

---

## [2026-04-24] Hard cap of 2 follow-up questions

**Context:** Could ask unlimited questions until the score hits 80.  
**Choice:** Hard cap at 2 follow-up questions regardless of score.  
**Reasoning:** More than 2 questions starts feeling like a form, not a conversation. Decision fatigue is the problem we're solving — an agent that asks 5 questions before showing anything recreates the same problem. If we can't hit 80 in 2 questions, we proceed with what we have.  
**Tradeoff:** Some very vague queries will get a lower-confidence recommendation. We show the score honestly so the user knows.

---

## [2026-04-24] 1 recommendation, not a list of 3

**Context:** Standard UX is "top 3 recommendations."  
**Choice:** 1 primary recommendation + an elimination panel for everything else.  
**Reasoning:** Showing 3 options recreates the decision paralysis we're solving. If the agent is confident, it commits. The elimination panel satisfies curiosity ("why not the others?") without asking the user to choose again.  
**Tradeoff:** If the top recommendation is wrong for the user, there's no immediate fallback visible. We mitigate with "Start over", honest regret scenarios, and transparent confidence score.

---

## [2026-04-24] Follow-up questions ordered by confidence impact

**Context:** When multiple fields are missing, which to ask about first?  
**Choice:** Ask in order of confidence impact: use_case (25 pts) → budget (20 pts) → everything else.  
**Reasoning:** The question that unlocks the most confidence points should be asked first. Asking about "occasion" (worth maybe 5 pts) before budget (worth 20 pts) wastes the user's patience.  
**Tradeoff:** None significant.

---

## [2026-04-24] Web Speech API for voice input — no external service

**Context:** Voice input could be implemented via Google Cloud Speech-to-Text, Whisper API, etc.  
**Choice:** Browser's native Web Speech API (free, built into Chrome/Edge).  
**Reasoning:** Zero cost, zero API key, zero latency overhead. Works offline in Chrome. For a hackathon demo, it's the cleanest solution — no billing risk, no setup. Users tap mic, speak, and the transcript appears in the input box.  
**Tradeoff:** Only works in Chrome and Edge (not Safari, not Firefox). We show the mic button only when the API is detected, so it degrades gracefully.

---

## [2026-04-24] Smart site routing: OLX check before vehicle check

**Context:** "Used car under 5 lakhs" should go to OLX, not CarWale (which is for new car research).  
**Choice:** Check for used/second-hand keywords first, before any vehicle keywords.  
**Reasoning:** A user asking for a "used car" has fundamentally different needs from someone researching "new cars." OLX lists actual for-sale used cars with real seller prices. CarWale is for new car specs and dealer pricing. Getting this order wrong would be a demo-breaking bug.  
**Tradeoff:** None — the order of checks directly maps to user intent categories.

---

## [2026-04-24] Curated demo fallback pool

**Context:** Live Playwright browsing fails when sites block headless browsers.  
**Choice:** 35+ realistic Indian products across carwale/olx/amazon/flipkart as fallback data.  
**Reasoning:** A demo that dead-ends with "couldn't find products" fails the judging. The fallback ensures every query gets a result. Products are real (real models, real price ranges from April 2026) and filtered by keyword against the intent before returning.  
**Tradeoff:** Fallback products don't have real-time prices. We show a "curated listings" status message so it's transparent.
