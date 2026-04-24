# ShopSense — Decision Log

Every significant decision made during the build. Written in real-time, not retroactively.

---

## [2026-04-24] Decision: Monorepo structure (frontend + backend in one repo)
**Context:** Could split into two repos for cleaner separation.
**Choice:** Single repo with `/frontend` and `/backend` folders.
**Reasoning:** Simpler for judges to review, single GitHub link in submission, easier to show the full system at once.
**Tradeoff:** Slightly messier deploys (Vercel and Render need root directory configured).

---

## [2026-04-24] Decision: FastAPI (Python) over Express (Node.js) for backend
**Context:** Both are valid. Node would match the frontend language.
**Choice:** FastAPI (Python).
**Reasoning:** Team is stronger in Python. FastAPI has first-class async support and native SSE via StreamingResponse. Pydantic v2 gives us strong request validation for free.
**Tradeoff:** Two different runtimes to manage. Backend can't share types with frontend directly.

---

## [2026-04-24] Decision: Server-Sent Events (SSE) over WebSockets for streaming
**Context:** Real-time streaming needed for confidence meter + LLM token streaming.
**Choice:** SSE (Server-Sent Events).
**Reasoning:** The communication is one-directional (server → client). SSE is simpler to implement, works over standard HTTP, and is supported by all modern browsers without extra libraries. WebSockets are overkill for a request-response + stream pattern.
**Tradeoff:** Can't push server-initiated messages outside of a request. Acceptable for our use case.

---

## [2026-04-24] Decision: Shopify Storefront API over Admin API
**Context:** Shopify offers both Admin (full access) and Storefront (public read + cart) APIs.
**Choice:** Storefront API.
**Reasoning:** We only need read access to product listings and cart creation. Storefront API doesn't require merchant authentication tokens — it uses a public access token, which is appropriate for a buyer-facing agent. Admin API would be over-privileged.
**Tradeoff:** No access to order history, customer data, or inventory management. All acceptable for Track 1 scope.

---

## [2026-04-24] Decision: Claude Haiku over GPT-4o-mini for LLM
**Context:** Both are fast, cheap models suited for high-frequency calls.
**Choice:** claude-haiku-4-5-20251001.
**Reasoning:** Haiku is faster at structured JSON output (critical for intent extraction). Claude models follow system prompt instructions more reliably for our constrained output formats. Also aligns with the Kasparro/Anthropic ecosystem.
**Tradeoff:** Slightly higher per-token cost than GPT-4o-mini. Negligible at hackathon scale.

---

## [2026-04-24] Decision: Confidence score is deterministic (no LLM)
**Context:** Could have asked the LLM "how confident are you in this recommendation?"
**Choice:** Deterministic algorithm in confidence_engine.py.
**Reasoning:** LLM confidence estimates are unreliable and can't be explained. A deterministic formula (category match + budget match + use case match + priority match − ambiguity penalty) is transparent, auditable, and consistent. Judges can read the formula and understand exactly why a score is what it is. This is also a cleaner AI/deterministic boundary.
**Tradeoff:** The formula is an approximation of "fit." A perfectly matched product might score lower if it has unusual tags. We accept this in exchange for transparency.

---

## [2026-04-24] Decision: Confidence threshold of 80 to commit to recommendation
**Context:** Need to decide when to stop asking follow-up questions.
**Choice:** Score ≥ 80 triggers recommendation without further questions.
**Reasoning:** Below 80 means there's meaningful ambiguity that a targeted question can resolve. Above 80, we have enough signal. 80 is not arbitrary — it corresponds to having full category + budget + use case data with no unresolved ambiguities, or having 2 of 3 with minimal missing info.
**Tradeoff:** Some borderline cases (score 78) might benefit from one more question. We accept this to avoid over-asking.

---

## [2026-04-24] Decision: Max 2 follow-up questions hard cap
**Context:** Could ask as many questions as needed to hit 80% confidence.
**Choice:** Hard cap at 2 follow-up questions regardless of score.
**Reasoning:** More than 2 questions starts feeling like a form, not a conversation. The original problem we're solving is decision fatigue — an agent that makes you answer 5 questions before showing anything reproduces the same fatigue. If we can't get to 80 in 2 questions, we proceed with what we have.
**Tradeoff:** Some very vague queries will be recommended with lower confidence. We surface this honestly in the UI (score shown).

---

## [2026-04-24] Decision: Show 1 recommendation, not a list of 3
**Context:** Standard approach is to show "top 3 recommendations."
**Choice:** 1 primary recommendation with a full elimination panel for the rest.
**Reasoning:** Showing 3 options recreates the decision paralysis we're solving. If the agent is confident, it commits to one answer. The elimination panel satisfies curiosity ("why not the others?") without asking the user to choose.
**Tradeoff:** If the top recommendation is wrong, there's no fallback visible. We mitigate this with the "start over" option and honest regret scenario.

---

## [2026-04-24] Decision: Elimination reasons are deterministic, not LLM-generated
**Context:** Could ask the LLM to explain why each product was eliminated.
**Choice:** Deterministic logic in product_ranker._build_elimination_list().
**Reasoning:** LLM-generated elimination reasons are slow (N products × 1 LLM call) and can hallucinate. Our confidence sub-scores already tell us exactly why a product didn't fit: price over budget, use case mismatch, constraint violation. We just surface those labels.
**Tradeoff:** Reasons are less nuanced than LLM-generated ones. "Use case mismatch" is less explanatory than "This shoe is designed for gym training, not road running." Future improvement: hybrid approach.

---

## [2026-04-24] Decision: Next.js App Router over Pages Router
**Context:** Next.js supports both routing paradigms.
**Choice:** App Router (Next.js 14).
**Reasoning:** App Router is the current standard. Better support for streaming responses and server components. More aligned with where the ecosystem is heading.
**Tradeoff:** Slightly steeper learning curve, fewer StackOverflow answers for edge cases.

---

## [2026-04-24] Decision: framer-motion for confidence ring animation
**Context:** Could use CSS transitions only or a canvas-based approach.
**Choice:** framer-motion useMotionValue + CSS SVG stroke-dashoffset transition.
**Reasoning:** The confidence ring animation is the centrepiece of the demo. It needs to feel smooth and satisfying. framer-motion handles spring physics and count-up animations elegantly. CSS transitions alone can't do the number count-up.
**Tradeoff:** Adds ~30kb to bundle. Acceptable.

---
