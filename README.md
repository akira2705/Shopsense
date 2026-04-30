# ShopSense — AI Purchase Confidence Engine

> **Most shopping agents show you more options. ShopSense eliminates everything wrong for you until only one confident recommendation remains.**

**Live demo:** [https://shopsense-eight.vercel.app ]
**Hackathon:** Kasparro Agentic Commerce — Track 1 — April 2026  
**Team:** Shivaathmajan P & Ayswaryaa V — B.Tech IT, Kumaraguru College of Technology

---

## The Problem

Shopping online means drowning in choices. You search "running shoes", get 2,000 results, read 40 reviews, open 12 tabs, and still aren't sure. Decision paralysis is the real problem — not lack of options.

## The Solution

ShopSense is an AI shopping agent that **commits to one recommendation** with a transparent confidence score and explains exactly why everything else was ruled out. It queries a Shopify product store, scores every product deterministically against your specific needs, and reasons about fit in real time — not generic popularity.

---

## What Makes It Different

| Typical shopping agent | ShopSense |
|---|---|
| Shows 20 results | Shows **1 recommendation** |
| Ranks by popularity | Ranks by confidence against *your* needs |
| "Here are some options" | "I'm 84% confident — here's why everything else was ruled out" |
| Generic reasoning | Regret-risk framing + honest tradeoff |
| Static product data | Live Shopify store + AI browser fallback |
| Just text | Animated confidence ring that builds as you talk |

---

## Live Demo

**Try these at https://shopsense-eight.vercel.app:**

| Say this | What it demonstrates |
|---|---|
| `Running shoes for flat feet under ₹5000` | Constraint handling + budget filter |
| `Gaming laptop with RTX GPU under ₹80000` | Tech synonym expansion (GPU → RTX) |
| `Skincare for oily skin under ₹1000` | Follow-up question flow |
| `Sony noise cancelling headphones` | Brand constraint enforcement |
| `Laptop for college under ₹45000` | Use-case + budget scoring |
| Or tap the 🎤 mic and speak your request | Voice input |

---

## Architecture

```
User (voice or text)
        │
        ▼
Next.js 15 frontend (Vercel)
  • Animated confidence ring
  • Live status stream
  • Quick-start chips + voice input (Web Speech API)
        │  SSE streaming
        ▼
FastAPI backend (Railway)
  • Intent extraction  →  Groq LLM (llama-3.3-70b)
  • Confidence score   →  Pure deterministic math, zero LLM
  • Follow-up Q&A      →  Groq LLM if score < 80
        │
        ├── PRIMARY: Shopify Admin API
        │     shopsense-rueprzpz.myshopify.com
        │     90+ products: shoes, skincare, phones, laptops, headphones
        │     Instant query — no browser, no wait
        │
        └── FALLBACK: Browser Agent (Playwright + Groq Vision)
              Google → top product site links → parallel screenshots
              Groq Vision (llama-4-scout-17b) reads each page
              Supports: Amazon.in, Flipkart, CarWale, OLX
        │
        ▼
Back to FastAPI
  • Deterministic re-score with real products
  • Brand filter — hard removes wrong-brand results
  • Stream reasoning token by token  →  Groq LLM
  • Generate elimination reasons     →  Groq LLM
        │
        ▼
User sees:
  ✓ 1 recommendation
  ✓ Animated confidence score (0–100%)
  ✓ Why it was picked (live-streamed reasoning)
  ✓ Why everything else was ruled out
  ✓ Regret risk + honest tradeoff
  ✓ Rating + buyer review highlight
  ✓ "View on Shopify / Amazon / Flipkart" button
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind v4 | App Router, full SSE support |
| Animations | Framer Motion | Confidence ring, token streaming, status slides |
| Backend | FastAPI, Python 3.11, Pydantic v2 | Async-native, StreamingResponse for SSE |
| Product data | Shopify Admin GraphQL API | Structured, instant, hackathon requirement |
| LLM | Groq `llama-3.3-70b-versatile` | Free tier, fastest inference, OpenAI-compatible |
| Vision | Groq `meta-llama/llama-4-scout-17b-16e-instruct` | Reads product screenshots directly |
| Browser | Playwright (headless Chromium) | Real browser fallback when Shopify has no match |
| Streaming | Server-Sent Events | Live status + token-by-token reasoning |
| Voice | Web Speech API | Free, browser-native, no API key needed |
| Frontend deploy | Vercel | Auto-deploys from GitHub |
| Backend deploy | Railway | Persistent Playwright + env var management |

---

## How the Confidence Score Works

The score is **100% deterministic — no LLM involved.** Every point is explainable.

```
Category match:    0–25 pts   product category matches stated need
Budget match:      0–20 pts   products within stated budget
Use case match:    0–25 pts   description/tags match use case
Priority match:    0–15 pts   features match stated priorities (per-priority, partial credit)
Rating bonus:      0–5 pts    4.5★ with 1000+ reviews → +5
Ambiguity penalty: −8 pts     per unresolved missing field
Constraint penalty:−15 pts    per hard constraint no product meets

Threshold to commit: ≥ 80 pts
Max follow-up questions: 2
```

When the ring hits 80%, it pulses green. The sidebar shows a **Score Breakdown** and a **Confidence Journey** across the conversation.

Tech synonym expansion ensures "GPU" matches "NVIDIA RTX 4070", "SSD" matches "NVMe 512GB", "screen quality" matches "OLED 144Hz" — so priority scoring is accurate even when product descriptions don't use the user's exact words.

---

## Shopify Integration

ShopSense queries a live Shopify dev store as its primary product source:

- **Store:** `shopsense-rueprzpz.myshopify.com`
- **API:** Admin GraphQL API with `read_products` scope
- **Query strategy:** Builds `title:*keyword* OR tag:keyword` expressions from the extracted intent, with `vendor:Brand` as a hard AND filter for brand constraints
- **Metafields:** Each product carries `shopsense.rating`, `shopsense.review_count`, `shopsense.review_highlight` — used by the confidence engine and product card
- **Product URL:** `onlineStoreUrl` (real listing page) with slug-based fallback

The store contains 90+ hand-crafted products across running shoes, skincare, smartphones, laptops, and headphones — each with realistic INR pricing, detailed tags, and review metadata.

If Shopify returns no results (brand mismatch, out-of-budget), the browser agent fires as fallback.

---

## Voice Input

Tap the 🎤 microphone button and speak your request in English (Indian accent optimised with `en-IN` locale). The browser's built-in Speech Recognition (Chrome/Edge) transcribes it, fills the input, and auto-sends after 600ms — so you can see what was captured before it goes. No API key, no cost, zero latency.

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com) — free, no credit card required
- A Shopify dev store with Admin API token (optional — browser agent works without it)

### 1. Clone

```bash
git clone https://github.com/akira2705/Shopsense.git
cd Shopsense
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

Open `.env` and fill in your values:
```env
GROQ_API_KEY=gsk_your_key_here
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ADMIN_TOKEN=shpat_your_token_here
ALLOWED_ORIGINS=http://localhost:3000
```

Start the server:
```bash
# Windows
py start.py

# Mac / Linux
uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/health → `{"status":"ok"}`

#### Populate the Shopify store (first time only)
```bash
python scripts/populate_shopify.py
```
Creates 90 products with ratings and review metadata. Takes ~2 minutes.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Environment Variables

**`backend/.env`** (copy from `.env.example`):
```env
GROQ_API_KEY=gsk_...                    # Required — get free at console.groq.com
SHOPIFY_STORE_URL=store.myshopify.com   # Shopify dev store domain
SHOPIFY_ADMIN_TOKEN=shpat_...           # Admin API access token
ALLOWED_ORIGINS=http://localhost:3000   # Comma-separated allowed origins
```

**Frontend (Vercel env vars or `.env.local`)**:
```env
NEXT_PUBLIC_API_URL=https://your-railway-service.railway.app
```

---

## Deploy

### Backend → Railway

1. New project → connect GitHub repo
2. **Root directory:** `backend`
3. **Build command:** `pip install -r requirements.txt && playwright install chromium && playwright install-deps`
4. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment variables:** `GROQ_API_KEY`, `SHOPIFY_STORE_URL`, `SHOPIFY_ADMIN_TOKEN`, `ALLOWED_ORIGINS`

### Frontend → Vercel

1. Import GitHub repo
2. **Root directory:** `frontend`
3. Framework auto-detected as Next.js
4. **Environment variable:** `NEXT_PUBLIC_API_URL=https://your-service.railway.app`

---

## Project Structure

```
Shopsense/
├── backend/
│   ├── main.py                    FastAPI app + /api/chat SSE endpoint
│   ├── start.py                   Windows entry point (ProactorEventLoop for Playwright)
│   ├── .env.example               Environment variable template
│   ├── requirements.txt           Python dependencies
│   ├── agent/
│   │   ├── shopify_client.py      Shopify Admin GraphQL — primary product source
│   │   ├── browser_agent.py       Playwright + Groq Vision — browser fallback
│   │   ├── confidence_engine.py   Deterministic scoring formula (zero LLM)
│   │   ├── intent_extractor.py    Groq LLM → structured JSON intent
│   │   ├── followup_generator.py  Prioritised follow-up question logic
│   │   └── product_ranker.py      Streaming reasoning + AI elimination reasons
│   ├── prompts/
│   │   └── intent_prompt.txt      Intent extraction prompt
│   └── scripts/
│       └── populate_shopify.py    Bulk-create 90 products via REST API
│
├── frontend/
│   ├── app/page.tsx               Entry point
│   ├── lib/api.ts                 Typed SSE streaming client
│   └── components/
│       ├── ChatInterface.tsx      Main chat, voice input, quick chips, status
│       ├── ConfidenceMeter.tsx    Animated ring + breakdown + journey
│       ├── ProductCard.tsx        Recommendation card + source badge + rating
│       └── EliminationPanel.tsx   Ruled-out products with AI reasons
│
└── README.md                      This file
```

---

## SSE Event Protocol

The backend streams real-time events to the frontend:

| Event type | When | Payload |
|---|---|---|
| `confidence` | After intent extracted | `score`, `breakdown` |
| `followup` | If score < 80 and < 2 questions asked | `question` |
| `status` | While searching / browsing | `text` (e.g. "Searching store…") |
| `message` | Agent commentary | `content` |
| `recommendation_start` | Product picked | `product`, `elimination` |
| `token` | Reasoning streaming | `text` (one chunk) |
| `recommendation_done` | Stream complete | `regret_risk`, `tradeoff` |
| `done` | Request complete | — |

---

## Team

| Name | Role |
|---|---|
| **Shivaathmajan P** | Full-stack, backend agent pipeline, Shopify integration, LLM |
| **Ayswaryaa V** | Frontend, UI/UX, animations, confidence meter |

B.Tech Information Technology — 3rd Year  
Kumaraguru College of Technology, Coimbatore

**Kasparro Agentic Commerce Hackathon — Track 1 — April 2026**
