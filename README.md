# ShopSense — AI Purchase Confidence Engine

> **Most shopping agents show you more options. ShopSense eliminates everything wrong for you until only one confident recommendation remains.**

**Live demo:** [https://shopsense-eight.vercel.app ]
**Hackathon:** Kasparro Agentic Commerce — Track 1 — April 2026  
**Team:** Shivaathmajan P & Ayswaryaa V — B.Tech IT, Kumaraguru College of Technology

---

## The Problem

Shopping online means drowning in choices. You search "running shoes", get 2,000 results, read 40 reviews, open 12 tabs, and still aren't sure. Decision paralysis is the real problem — not lack of options.

## The Solution

ShopSense is an AI agent that **commits to one recommendation** with a transparent confidence score and explains exactly why everything else was ruled out. It browses real product sites live, reads them with AI vision, and reasons about fit against *your specific needs* — not generic popularity.

---

## What Makes It Different

| Typical shopping agent | ShopSense |
|---|---|
| Shows 20 results | Shows **1 recommendation** |
| Ranks by popularity | Ranks by confidence against *your* needs |
| "Here are some options" | "I'm 84% confident — here's why everything else was ruled out" |
| Generic reasoning | Regret-risk framing + honest tradeoff |
| Static product data | AI browses live sites and reads what it sees |
| Just text | Animated confidence ring that builds as you talk |

---

## Live Demo

**Try these at https://shopsense-eight.vercel.app:**

| Say this | What it demonstrates |
|---|---|
| `Running shoes for flat feet under ₹5000` | Constraint handling + budget filter |
| `Used car under 5 lakhs in good condition` | Routes to OLX, not Amazon |
| `Laptop for college under ₹45000` | Routes to Flipkart, shows laptops |
| `Skincare for oily skin` | Follow-up question flow |
| `Just show me something good` | Vague intent → targeted Q&A → recommendation |
| Or tap the 🎤 mic and speak your request | Voice input |

---

## Architecture

```
User (voice or text)
        │
        ▼
Next.js 15 frontend (Vercel)
  • Animated confidence ring
  • Live browser status stream
  • Quick-start chips + voice input
        │  SSE streaming
        ▼
FastAPI backend (Render)
  • Intent extraction  →  Groq LLM (llama-3.3-70b)
  • Confidence score   →  Pure math, zero LLM
  • Follow-up Q&A      →  Groq LLM if score < 80
  • Browser agent      →  Playwright (real Chrome)
        │
        ▼
Product Sites (live browsing)
  OLX.in ──────── used / second-hand items
  CarWale.com ──── new cars & bikes
  Flipkart.com ─── laptops, TVs, appliances, fashion
  Amazon.in ─────── everything else
        │
        ▼
Groq Vision (llama-3.2-90b-vision-preview)
  • Screenshot → prices, ratings, reviews
        │
        ▼
Back to FastAPI
  • Re-score with real products
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
  ✓ "View on Amazon / Flipkart / CarWale / OLX" button
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind v4 | App Router, full SSE support |
| Animations | Framer Motion | Confidence ring, token streaming, status slides |
| Backend | FastAPI, Python 3.11, Pydantic v2 | Async-native, StreamingResponse for SSE |
| LLM | Groq `llama-3.3-70b-versatile` | Free tier, fastest inference, OpenAI-compatible |
| Vision | Groq `llama-3.2-90b-vision-preview` | Reads product screenshots directly |
| Browser | Playwright (headless Chromium) | Real browser automation, not scraping |
| Streaming | Server-Sent Events | Live status + token-by-token reasoning |
| Voice | Web Speech API | Free, browser-native, no API key needed |
| Frontend deploy | Vercel | Auto-deploys from GitHub |
| Backend deploy | Render | Free tier with Playwright support |

---

## How the Confidence Score Works

The score is **100% deterministic — no LLM involved.** Every point is explainable.

```
Category match:    0–25 pts   product category matches stated need
Budget match:      0–20 pts   products within stated budget
Use case match:    0–25 pts   description/tags match use case
Priority match:    0–15 pts   features match stated priorities
Ambiguity penalty: −8 pts     per unresolved missing field

Threshold to commit: ≥ 80 pts
Max follow-up questions: 2
```

When the ring hits 80%, it pulses green and shows **"✓ Ready to recommend"**.

The sidebar shows a **Score Breakdown** (each component as a bar) and a **Confidence Journey** (how the score evolved across the conversation).

---

## Smart Site Routing

The browser agent routes to the right platform automatically:

```
"used car under 5 lakhs"       → OLX.in          (used/second-hand: highest priority)
"new Swift on a budget"        → CarWale          (vehicles)
"laptop for college"           → Flipkart         (laptops/TVs/appliances/fashion)
"running shoes for flat feet"  → Amazon.in        (everything else)
```

If live browsing fails (site blocks headless browser), it falls back to a curated demo pool of **35+ realistic Indian products** across all categories — the demo never dead-ends.

---

## Voice Input

Tap the 🎤 microphone button and speak your request in English. The browser's built-in Speech Recognition (Chrome/Edge) transcribes it, fills the input, and auto-sends after 600ms — so you can see what was captured before it goes. No API key, no cost, zero latency.

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com) — free, no credit card required

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

Open `.env` and add your Groq API key:
```env
GROQ_API_KEY=gsk_your_key_here
ALLOWED_ORIGINS=http://localhost:3000
```

Start the server:
```bash
# Windows — use start.py so Playwright's Chromium works correctly
py start.py

# Mac / Linux
uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/health → `{"status":"ok"}`

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

> **Windows note:** Playwright requires the ProactorEventLoop to spawn Chromium. This is already handled in `main.py` — no extra config needed.

---

## Environment Variables

**`backend/.env`** (copy from `.env.example`):
```env
GROQ_API_KEY=gsk_...          # Required — get free at console.groq.com
ALLOWED_ORIGINS=http://localhost:3000   # Comma-separated allowed origins
```

**Frontend (Vercel env vars or `.env.local`)**:
```env
NEXT_PUBLIC_API_URL=https://your-render-service.onrender.com
```

---

## Deploy

### Backend → Render (free tier)

1. New Web Service → connect GitHub repo
2. **Root directory:** `backend`
3. **Build command:** `pip install -r requirements.txt && playwright install chromium && playwright install-deps`
4. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment variables:** `GROQ_API_KEY`, `ALLOWED_ORIGINS` (your Vercel URL)

### Frontend → Vercel (free)

1. Import GitHub repo
2. **Root directory:** `frontend`
3. Framework auto-detected as Next.js
4. **Environment variable:** `NEXT_PUBLIC_API_URL=https://your-service.onrender.com`

> **Render cold-starts:** Free tier sleeps after 15 min of inactivity. Hit `/health` endpoint once before a demo to wake it up (~30s).

---

## Project Structure

```
Shopsense/
├── backend/
│   ├── main.py                    FastAPI app + /api/chat SSE endpoint
│   ├── .env.example               Environment variable template
│   ├── requirements.txt           Python dependencies
│   └── agent/
│       ├── browser_agent.py       Playwright browser + Groq Vision + site routing
│       ├── confidence_engine.py   Deterministic scoring formula (zero LLM)
│       ├── intent_extractor.py    Groq LLM → structured JSON intent
│       ├── followup_generator.py  Prioritised follow-up question logic
│       └── product_ranker.py      Streaming reasoning + AI elimination reasons
│   └── prompts/
│       ├── intent_prompt.txt      Intent extraction prompt
│       ├── followup_prompt.txt    Follow-up question prompt
│       ├── ranker_prompt.txt      Recommendation reasoning prompt
│       └── elimination_prompt.txt AI elimination reason prompt
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
├── DECISIONS.md                   Every build decision logged with reasoning
└── README.md                      This file
```

---

## SSE Event Protocol

The backend streams real-time events to the frontend:

| Event type | When | Payload |
|---|---|---|
| `confidence` | After intent extracted | `score`, `breakdown` |
| `followup` | If score < 80 and < 2 questions asked | `question` |
| `status` | While browser agent runs | `text` (e.g. "Opening Amazon.in…") |
| `message` | Agent commentary | `content` |
| `recommendation_start` | Recommendation picked | `product`, `elimination` |
| `token` | Reasoning streaming | `text` (one chunk) |
| `recommendation_done` | Stream complete | `regret_risk`, `tradeoff` |
| `done` | Request complete | — |

---

## Design Decisions

See [DECISIONS.md](./DECISIONS.md) for the full log — every significant architectural choice with context, reasoning, and tradeoffs, written during the build.

Key decisions:
- **Groq over OpenAI** — free tier, no credit card, same API interface
- **Playwright + Vision over product APIs** — real browsing means real prices, real availability
- **Deterministic confidence score** — transparent, auditable, no hallucination
- **1 recommendation, not 3** — solves decision paralysis, doesn't recreate it
- **SSE over WebSockets** — one-directional stream, simpler, works over standard HTTP

---

## Team

| Name | Role |
|---|---|
| **Shivaathmajan P** | Full-stack, backend agent pipeline, LLM integration |
| **Ayswaryaa V** | Frontend, UI/UX, animations, confidence meter |

B.Tech Information Technology — 3rd Year  
Kumaraguru College of Technology, Coimbatore

**Kasparro Agentic Commerce Hackathon — Track 1 — April 2026**
