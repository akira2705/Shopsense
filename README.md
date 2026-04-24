# ShopSense — AI Purchase Confidence Engine

> ShopSense optimises for purchase confidence, not product discovery.

Most shopping agents help you find more options. ShopSense eliminates everything wrong for you until only one confident recommendation remains — with a live confidence score, transparent reasoning, and a full elimination log.

**Live demo:** https://shopsense.vercel.app  
**Demo video:** [Link after recording]

---

## Architecture

```
User → Next.js (Vercel) → FastAPI (Render) → Anthropic API + Shopify Storefront API
```

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind, Framer Motion | Chat UI + animated confidence meter |
| Backend | FastAPI, Python 3.11, Pydantic v2 | Agent pipeline + SSE streaming |
| LLM | Claude Haiku (Anthropic) | Intent extraction + reasoning generation |
| Products | Shopify Storefront API (GraphQL) | Product search + cart creation |
| Streaming | Server-Sent Events | Real-time confidence + LLM token stream |

---

## How it works

1. User states shopping intent in natural language
2. Backend extracts structured intent (LLM) and computes an initial confidence score (deterministic)
3. If confidence < 80%, agent asks one targeted follow-up question (max 2 questions total)
4. Shopify is queried for matching products
5. Confidence is re-scored against actual products
6. Top product is selected; LLM generates specific reasoning using a viability/regret framework
7. All other products are eliminated with deterministic reasons surfaced in the UI
8. User sees: 1 recommendation, confidence score + breakdown, elimination panel, Add to Cart button

---

## Confidence Score Formula

The confidence score is **fully deterministic — no LLM involved**.

```
Category match:    0–25 pts  (product category matches stated need)
Budget match:      0–20 pts  (products within stated budget)
Use case match:    0–25 pts  (product description/tags match use case)
Priority match:    0–15 pts  (product features match stated priorities)
Ambiguity penalty: -8 pts    per unresolved missing_info item

Threshold to commit: ≥ 80 pts
Max follow-up questions: 2
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Shopify dev store + Storefront API token
- Anthropic API key

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in your keys in .env
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000

---

## Try these example prompts

1. `Running shoes for flat feet under ₹5,000`
2. `I need a gift for my mom who likes skincare but is picky about ingredients`
3. `Build me a skincare routine for oily skin`
4. `Just show me something good` ← tests vague intent handling
5. `I want premium quality but also budget-friendly` ← tests contradictory constraints

---

## Deploy

**Backend → Render**
- Root directory: `backend/`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `SHOPIFY_STOREFRONT_TOKEN`, `SHOPIFY_STORE_URL`, `ANTHROPIC_API_KEY`, `ALLOWED_ORIGINS`

**Frontend → Vercel**
- Root directory: `frontend/`
- Framework: Next.js (auto-detected)
- Environment variable: `NEXT_PUBLIC_API_URL=https://your-service.onrender.com`

> Note: Render free tier cold-starts in ~30s after inactivity. Hit `/health` before demoing to warm it up.

---

## Project Structure

```
shopsense/
├── backend/
│   ├── main.py                    FastAPI app + SSE endpoint
│   ├── agent/
│   │   ├── confidence_engine.py   Deterministic scoring (no LLM)
│   │   ├── intent_extractor.py    LLM → structured JSON intent
│   │   ├── followup_generator.py  Decides follow-up questions
│   │   ├── product_ranker.py      Ranks + generates reasoning
│   │   └── shopify_client.py      Async Shopify GraphQL client
│   ├── prompts/                   LLM prompt templates
│   └── requirements.txt
├── frontend/
│   ├── app/page.tsx               Entry point
│   ├── components/
│   │   ├── ChatInterface.tsx      SSE client + message state
│   │   ├── ConfidenceMeter.tsx    Animated ring + breakdown
│   │   ├── ProductCard.tsx        Recommendation display
│   │   └── EliminationPanel.tsx   Ruled-out products
│   └── lib/api.ts                 Typed SSE streaming client
├── DECISIONS.md                   Build decision log (15+ entries)
└── README.md
```

---

## Team

- Shivaathmajan P — B.Tech IT 3rd Year, Kumaraguru College of Technology
- Ayswaryaa V — B.Tech IT 3rd Year, Kumaraguru College of Technology

Kasparro Agentic Commerce Hackathon — Track 1 — April 2026
