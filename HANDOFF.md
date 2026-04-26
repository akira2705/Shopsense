# ShopSense — Handoff Brief
> Paste this entire file into a new chat to continue exactly where we left off.

---

## Who I Am
- **Name:** Shivaathmajan P
- **Email:** shivaathmajan@gmail.com
- **Team:** Shivaathmajan P + Ayswaryaa V — B.Tech IT 3rd Year, Kumaraguru College of Technology
- **Hackathon:** Kasparro Agentic Commerce Hackathon — Track 1 (AI Shopping Agent)
- **Deadline:** 30 April 2026, 11:59 PM IST

---

## Project: ShopSense — AI Purchase Confidence Engine

**Core concept:** ShopSense optimises for *purchase confidence*, not product discovery.  
Most shopping agents show you more options. ShopSense eliminates everything wrong for you until one confident recommendation remains — with a live confidence score, transparent reasoning, and a full elimination log.

**One-line pitch:** "I'll tell you when I'm confident enough to recommend."

**GitHub:** https://github.com/akira2705/Shopsense

---

## Architecture

```
User → Next.js (Vercel) → FastAPI (Render) → Anthropic API + Shopify Storefront API
```

| Layer | Tech | Purpose |
|---|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind v4, Framer Motion | Chat UI + animated confidence meter |
| Backend | FastAPI, Python 3.11, Pydantic v2 | Agent pipeline + SSE streaming |
| LLM | Claude Haiku (claude-haiku-4-5-20251001) | Intent extraction + reasoning |
| Products | Shopify Storefront API (GraphQL) | Product search + cart creation |
| Streaming | Server-Sent Events | Real-time confidence + token stream |

---

## Confidence Score Formula (fully deterministic — zero LLM)

```
Category match:    0–25 pts
Budget match:      0–20 pts
Use case match:    0–25 pts
Priority match:    0–15 pts
Ambiguity penalty: -8 pts per unresolved missing_info item

Threshold to commit: ≥ 80 pts
Max follow-up questions: 2
```

---

## Current Status — What's DONE

- [x] Full monorepo created at `C:\Kasparro\shopsense`
- [x] Backend: `main.py`, `confidence_engine.py`, `intent_extractor.py`, `followup_generator.py`, `product_ranker.py`, `shopify_client.py`
- [x] All LLM prompt templates: `intent_prompt.txt`, `followup_prompt.txt`, `reasoning_prompt.txt`
- [x] Frontend: `ChatInterface.tsx`, `ConfidenceMeter.tsx`, `ProductCard.tsx`, `EliminationPanel.tsx`, `lib/api.ts`
- [x] `README.md` with full setup + deploy instructions
- [x] `DECISIONS.md` with 13 build decision entries
- [x] Backend running locally: `py -m uvicorn main:app --reload --port 8000`
- [x] Frontend running locally: `npm run dev` at http://localhost:3000
- [x] UI renders correctly — confidence meter, chat interface, opening message all working
- [x] Pushed to GitHub: https://github.com/akira2705/Shopsense

---

## What's NOT Done (priority order)

### 🔴 CRITICAL — blocks everything
1. **Create `backend/.env`** with real keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   SHOPIFY_STORE_URL=https://your-store.myshopify.com/api/2024-01/graphql.json
   SHOPIFY_STOREFRONT_TOKEN=your-token
   ALLOWED_ORIGINS=http://localhost:3000
   ```
2. **Shopify Partner account + dev store** → https://partners.shopify.com
   - Create dev store
   - Add 20–25 products in one category (footwear or skincare recommended)
   - Create custom app → enable Storefront API → get token
3. **Run 5 full end-to-end test scenarios** once keys are in place

### 🟡 IMPORTANT — needed for submission
4. **Implement failure handling** (`backend/agent/` — all files need try/except):
   - Shopify timeout → fallback to broad search
   - LLM bad JSON → regex fallback (already partially done in intent_extractor)
   - Zero products found → graceful "couldn't find products" message
   - Contradictory constraints → surface in reasoning
5. **Polish UI** — mobile layout, loading states, typography
6. **Write Technical Document** (2–3 pages) — judges read this
7. **Finalize DECISIONS.md** — target 15+ entries (currently 13)
8. **Deploy backend to Render** → https://render.com (free tier)
   - Root: `backend/`, Build: `pip install -r requirements.txt`, Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Set env vars: ANTHROPIC_API_KEY, SHOPIFY_STORE_URL, SHOPIFY_STOREFRONT_TOKEN, ALLOWED_ORIGINS
9. **Deploy frontend to Vercel** → https://vercel.com
   - Root: `frontend/`, set `NEXT_PUBLIC_API_URL=https://your-render-url.onrender.com`
10. **Record demo video** on live production URL
11. **Submit** to grandmaster@kasparro.com

---

## File Structure

```
C:\Kasparro\shopsense\
├── backend/
│   ├── main.py                    FastAPI + SSE endpoint
│   ├── .env.example               Copy to .env and fill keys
│   ├── requirements.txt
│   ├── agent/
│   │   ├── confidence_engine.py   Deterministic scoring (no LLM)
│   │   ├── intent_extractor.py    Claude Haiku → structured JSON
│   │   ├── followup_generator.py  Follow-up question logic
│   │   ├── product_ranker.py      Ranks + generates reasoning
│   │   └── shopify_client.py      Async GraphQL client
│   └── prompts/
│       ├── intent_prompt.txt
│       ├── followup_prompt.txt
│       └── reasoning_prompt.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx               Entry → <ChatInterface />
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── ChatInterface.tsx      SSE client + message state
│   │   ├── ConfidenceMeter.tsx    Animated SVG ring
│   │   ├── ProductCard.tsx        Recommendation + elimination
│   │   └── EliminationPanel.tsx   Ruled-out products
│   ├── lib/api.ts                 Typed SSE streaming client
│   └── package.json
├── README.md
├── DECISIONS.md
├── HANDOFF.md                     ← this file
└── .gitignore
```

---

## How to Run Locally

**Backend:**
```cmd
cd C:\Kasparro\shopsense\backend
py -m uvicorn main:app --reload --port 8000
```
Health check: http://localhost:8000/health → `{"status":"ok"}`

**Frontend** (separate terminal):
```cmd
cd C:\Kasparro\shopsense\frontend
npm run dev
```
Open: http://localhost:3000

**Push to GitHub:**
```cmd
cd C:\Kasparro\shopsense
git add .
git commit -m "your message"
git push origin main
```

---

## SSE Event Types (frontend listens for these)

| Event | Payload | When |
|---|---|---|
| `confidence` | `{score, breakdown, ambiguity_count}` | After intent extraction + after product search |
| `message` | `{text}` | Follow-up question or commit message |
| `followup` | `{question}` | When confidence < 80 and followups < 2 |
| `recommendation` | `{product, reasoning, regret_risk, ...}` | Final recommendation |
| `done` | `{}` | Pipeline complete |
| `error` | `{message}` | Any failure |

---

## Key Decisions Already Made

1. Monorepo (not separate repos)
2. FastAPI not Express — async generators for SSE
3. SSE not WebSockets — simpler, unidirectional
4. Storefront API not Admin API — public read, no credentials exposed
5. Claude Haiku not GPT — speed + cost for hackathon
6. Confidence score is 100% deterministic — no LLM
7. 80 pt threshold to commit
8. Hard cap of 2 follow-up questions
9. 1 recommendation not 3 — forces conviction
10. Elimination reasons are deterministic — not LLM generated
11. Next.js App Router
12. Framer Motion for confidence ring animation
13. Viability/regret framing for reasoning

---

## Days Left: ~5 days (deadline 30 April 2026)

### Suggested daily plan:
- **Today:** Get Shopify + .env done → first real end-to-end test
- **Tomorrow:** Fix all edge cases + failure handling
- **Day 3:** Deploy to Render + Vercel → test production
- **Day 4:** Technical Document + DECISIONS.md polish
- **Day 5:** Demo video + final submission
