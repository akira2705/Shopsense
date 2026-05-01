# ShopSense — Product Document

**Hackathon:** Kasparro Agentic Commerce — Track 1 — April 2026  
**Team:** Shivaathmajan P & Ayswaryaa V  
**Institution:** B.Tech IT, Kumaraguru College of Technology, Coimbatore

---

## 1. Problem Statement

Online shopping in India produces decision paralysis, not decisions.

A user searching for running shoes on Amazon gets 2,000+ results. They open 12 tabs, read 40 reviews across 3 sites, watch 2 YouTube comparisons, and still feel uncertain. The problem isn't a lack of information — it's an excess of it with no trusted interpreter.

Existing shopping tools make this worse:
- **Search engines** return sponsored results ranked by SEO, not fit
- **Price comparison tools** compare prices but not suitability
- **AI chatbots** list "top 5 options" and recreate the same paralysis with fewer results
- **Recommendation widgets** are trained on aggregate popularity, not individual needs

The gap: **no tool commits to a single recommendation and explains exactly why everything else was eliminated.**

---

## 2. Target User

**Primary:** Indian online shoppers (18–35) who are:
- Buying something they haven't bought before (first laptop, running shoes, skincare routine)
- Overwhelmed by options in a category they don't fully understand
- Willing to describe their needs in natural language
- Time-constrained — want a confident answer, not a research project

**Secondary:** Repeat buyers who want validation that they're not missing something better.

---

## 3. Solution: ShopSense

ShopSense is an AI shopping agent built on a single design principle:

> **Eliminate everything wrong. Commit to one.**

Instead of showing 10 options and leaving the decision to the user, ShopSense:

1. Extracts structured intent from natural conversation (budget, use case, constraints, priorities)
2. Computes a real-time **confidence score** — a number that tells both the agent and the user how well it understands the need
3. Asks targeted follow-up questions only when confidence is too low to commit (< 80%)
4. Searches a curated Shopify product store + live product sites as fallback
5. Scores every product deterministically against the extracted intent
6. Presents **one recommendation** with transparent reasoning, regret risk assessment, and why every alternative was ruled out

The confidence score is the central UI metaphor — it's an animated ring that fills as the user provides more context. When it hits 80%, it turns green and the agent commits.

---

## 4. Key User Flows

### Flow 1: Clear intent → instant recommendation
```
User: "Gaming laptop with RTX GPU under ₹80000"
→ Intent extracted (category: laptop, priority: GPU, budget: 80000)
→ Confidence: 72 (budget known, category known, use case partial)
→ Shopify query: vendor:ASUS OR vendor:Lenovo, tag:rtx, status:ACTIVE
→ Products scored → Lenovo LOQ 15 wins (RTX 4060, within budget, 144Hz)
→ Reasoning streamed live + elimination panel shown
```

### Flow 2: Vague intent → follow-up → recommendation
```
User: "I need skincare"
→ Intent extracted (category: skincare, use_case: missing, budget: missing)
→ Confidence: 18 (too ambiguous)
→ Follow-up: "Is this for oily, dry, or combination skin — and do you have a budget in mind?"
User: "Oily skin, under ₹500"
→ Confidence: 81 → commits
→ Recommends: Minimalist Niacinamide Serum (₹549, 4.6★, oily-skin tag)
```

### Flow 3: Brand constraint
```
User: "Sony headphones for travel"
→ brand: Sony extracted as hard constraint
→ Shopify query: vendor:Sony, tag:headphones,travel
→ Brand filter removes any non-Sony results
→ Sony WH-1000XM5 recommended with ANC + travel reasoning
```

---

## 5. Design Decisions

### 5.1 One recommendation, not three
The core product bet. Showing 3 options "just in case" would recreate decision paralysis. We show one, explain it fully, and show what was ruled out and why. If the user disagrees, they can push back in natural language.

### 5.2 Confidence score as primary UI metaphor
The score is computed deterministically (no LLM) and updated in real time. It gives the user a sense of whether the agent understands them — and gives the agent a principled threshold (80) for when to stop asking questions and commit.

### 5.3 Regret risk framing
Every recommendation includes a regret scenario ("You might regret this if: you plan to run trails — this is road-only") and an honest tradeoff. This is more valuable than a list of "cons" — it's personalised to the user's stated use case.

### 5.4 Shopify as primary source
Using a Shopify dev store means structured product data (vendor, tags, price, metafields) that the confidence engine can score precisely. The browser agent fires only when Shopify has no match — giving demo reliability without sacrificing live-browsing capability.

### 5.5 Elimination panel
Showing ruled-out products with one-sentence AI reasons ("Over budget — ₹89,999 exceeds your ₹80K limit") builds trust. The user can see the agent's reasoning, not just its conclusion.

---

## 6. Product Scope

### In scope
- Natural language shopping queries (text and voice)
- Shopify store product search with structured scoring
- Live browser fallback (Amazon, Flipkart, CarWale, OLX)
- Confidence score with breakdown and conversation journey
- Streaming AI reasoning
- Regret risk + tradeoff assessment
- Elimination panel with AI reasons
- Brand constraint enforcement
- Budget filtering
- Voice input (Web Speech API)

### Out of scope (v1)
- Order placement / cart management
- Price alerts or tracking
- Multi-recommendation comparison mode
- Product images (Shopify store products have no images in dev store)
- User accounts / history

---

## 7. Success Metrics

| Metric | Target |
|---|---|
| Time to first recommendation | < 30 seconds for clear intent |
| Follow-up questions before commit | ≤ 2 |
| Confidence at recommendation | ≥ 80% |
| Demo reliability | No dead-ends (Shopify fallback ensures this) |

---

## 8. Contribution

| Contributor | Focus |
|---|---|
| **Shivaathmajan P** | Backend pipeline (intent extraction, confidence engine, Shopify integration, browser agent), FastAPI SSE architecture, LLM prompt engineering, full-stack integration |
| **Ayswaryaa V** | Frontend (Next.js, TypeScript), UI/UX design, animated confidence meter, product card, elimination panel, voice input |

Both contributors participated in product thinking, feature scoping, and testing.
