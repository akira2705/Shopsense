# ShopSense — AI Purchase Confidence Engine

> ShopSense optimises for *purchase confidence*, not product discovery.

Most shopping agents show you more options. ShopSense eliminates everything wrong for you until only one confident recommendation remains — with a live confidence score, transparent reasoning, and a full elimination log.

**Live demo:** https://shopsense.vercel.app  
**Demo video:** [Link after recording]

---

## What makes it different

| Typical shopping agent | ShopSense |
|---|---|
| Shows 20 results | Shows 1 recommendation |
| Ranks by popularity | Ranks by confidence against *your* needs |
| "Here are some options" | "I'm 84% confident — here's why everything else was ruled out" |
| Generic reasoning | Regret-risk framing + honest tradeoff |
| Static product data | AI browses live sites and reads what it sees |

---

## Architecture

```
User → Next.js (Vercel) → FastAPI (Render) → Groq LLM + Browser Agent
                                                        ↓
                                         Playwright browses Amazon / Flipkart
                                         CarWale / OLX → screenshot →
                                         Groq Vision reads prices, ratings, reviews
```

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind v4, Framer Motion | Chat UI + animated confidence meter |
| Backend | FastAPI, Python 3.11, Pydantic v2 | Agent pipeline + SSE streaming |
| LLM | Groq — `llama-3.3-70b-versatile` | Intent extraction + reasoning + elimination |
| Vision | Groq — `llama-3.2-90b-vision-preview` | Reads product screenshots from real sites |
| Browser | Playwright (Chromium, headless) | Browses Amazon.in / Flipkart / CarWale / OLX |
| Streaming | Server-Sent Events | Live status updates + token-by-token reasoning |

---

## How it works

1. User states shopping intent in natural language
2. **Groq LLM** extracts structured intent (category, budget, use case, constraints)
3. A **deterministic confidence score** is computed — zero LLM involved
4. If confidence < 80%, agent asks one targeted follow-up (max 2 questions total)
5. **Playwright** launches a real browser and navigates to the right site:
   - General products → Amazon.in (fallback: Flipkart)
   - Cars / bikes → CarWale
   - Used / second-hand → OLX
6. A screenshot is taken; **Groq Vision** reads prices, ratings, and review counts from it
7. Products are re-scored against confidence formula with actual data
8. **Groq LLM streams** reasoning tokens live — the user watches it think in real-time
9. A second LLM call generates AI-powered elimination reasons for every ruled-out product
10. User sees: 1 recommendation · confidence score · star rating · "View on Amazon/Flipkart" · elimination panel

---

## Confidence Score Formula

The score is **100% deterministic — no LLM**.

```
Category match:    0–25 pts  (product category matches stated need)
Budget match:      0–20 pts  (products within stated budget)
Use case match:    0–25 pts  (description/tags match use case)
Priority match:    0–15 pts  (features match stated priorities)
Ambiguity penalty: –8 pts    per unresolved missing_info item

Threshold to commit: ≥ 80 pts
Max follow-up questions: 2
```

When the ring hits 80%, it pulses green and shows **"✓ Ready to recommend"**.

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Groq API key](https://console.groq.com) — free, no credit card

### Backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Add your GROQ_API_KEY in .env
py -m uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/health → `{"status":"ok"}`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Environment variables

**Backend `.env`:**
```env
GROQ_API_KEY=gsk_...
ALLOWED_ORIGINS=http://localhost:3000
```

**Frontend (Vercel):**
```env
NEXT_PUBLIC_API_URL=https://your-render-service.onrender.com
```

---

## Try these example prompts

| Prompt | What it tests |
|---|---|
| `Running shoes for flat feet under ₹5000` | Budget + constraint handling |
| `I need a smartphone under ₹12000 for photography` | Use-case matching |
| `Used car under 5 lakhs in good condition` | Routes to OLX via browser agent |
| `Best skincare for oily skin` | Follow-up question flow |
| `Just show me something good` | Vague intent → follow-up chain |
| `I want premium quality but cheap` | Contradictory constraints |

---

## Deploy

**Backend → Render (free tier)**
- Root directory: `backend/`
- Build command: `pip install -r requirements.txt && playwright install chromium && playwright install-deps`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `GROQ_API_KEY`, `ALLOWED_ORIGINS`

**Frontend → Vercel**
- Root directory: `frontend/`
- Framework: Next.js (auto-detected)
- Environment variable: `NEXT_PUBLIC_API_URL=https://your-service.onrender.com`

> **Note:** Render free tier cold-starts after ~15 min inactivity. Hit `/health` before demoing.

---

## Project Structure

```
shopsense/
├── backend/
│   ├── main.py                    FastAPI app + SSE endpoint
│   ├── agent/
│   │   ├── browser_agent.py       Playwright browser + Groq Vision extraction
│   │   ├── confidence_engine.py   Deterministic scoring (zero LLM)
│   │   ├── intent_extractor.py    Groq → structured JSON intent
│   │   ├── followup_generator.py  Follow-up question logic
│   │   └── product_ranker.py      Streaming reasoning + AI elimination reasons
│   ├── prompts/                   LLM prompt templates
│   └── requirements.txt
├── frontend/
│   ├── app/page.tsx               Entry point
│   ├── components/
│   │   ├── ChatInterface.tsx      SSE client, quick-start chips, status stream
│   │   ├── ConfidenceMeter.tsx    Animated ring + breakdown + celebration
│   │   ├── ProductCard.tsx        Recommendation + source badge + rating
│   │   └── EliminationPanel.tsx   Ruled-out products
│   └── lib/api.ts                 Typed SSE streaming client
├── DECISIONS.md                   Build decision log
└── README.md
```

---

## Team

- **Shivaathmajan P** — B.Tech IT 3rd Year, Kumaraguru College of Technology
- **Ayswaryaa V** — B.Tech IT 3rd Year, Kumaraguru College of Technology

Kasparro Agentic Commerce Hackathon — Track 1 — April 2026
