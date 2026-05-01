# ShopSense — Handoff Brief
> Paste this entire file into a new chat to continue exactly where we left off.

---

## Who I Am
- **Name:** Shivaathmajan P
- **Team:** Shivaathmajan P + Ayswaryaa V — B.Tech IT 3rd Year, Kumaraguru College of Technology
- **Hackathon:** Kasparro Agentic Commerce Hackathon — Track 1 (AI Shopping Agent)
- **Deadline:** 30 April 2026, 11:59 PM IST
- **GitHub:** https://github.com/akira2705/Shopsense
- **Live demo:** https://shopsense-eight.vercel.app

---

## Project: ShopSense — AI Purchase Confidence Engine

**Core concept:** ShopSense optimises for *purchase confidence*, not product discovery.
Most shopping agents show you more options. ShopSense eliminates everything wrong until one confident recommendation remains — with a live confidence score, transparent reasoning, and a full elimination log.

**One-line pitch:** "I'll tell you when I'm confident enough to recommend."

---

## Current Architecture

```
User → Next.js 15 (Vercel) → FastAPI (Railway) → Groq LLM + Shopify Admin API
```

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind v4, Framer Motion | Vercel deploy |
| Backend | FastAPI, Python 3.11, Pydantic v2 | Railway deploy |
| LLM | Groq `llama-3.3-70b-versatile` | OpenAI-compatible, free tier |
| Vision | Groq `meta-llama/llama-4-scout-17b-16e-instruct` | Browser agent screenshots |
| Products | Shopify Admin REST/GraphQL API | 199 products, shpat_ token |
| Browser fallback | Playwright + Groq Vision | When Shopify has no match |
| Streaming | Server-Sent Events | Token-by-token reasoning |
| Voice | Web Speech API (en-IN) | No API key |

---

## What's DONE

- [x] Full agent pipeline: intent extraction → confidence scoring → Shopify search → reasoning stream
- [x] Frontend: animated confidence ring, chat interface, ProductCard with TTS/Share/Ask/Cart
- [x] Budget optimizer card + budget adjustment chips (+₹5K etc.)
- [x] "Not this one" reject flow — fetches next pick
- [x] Voice input (Web Speech API, en-IN locale)
- [x] Shopify store: 199 products across phones, cars, shoes, skincare, laptops, headphones, board games, toys, home appliances, accessories
- [x] All 199 products have real product images (DuckDuckGo sourced, uploaded via Shopify REST)
- [x] All 199 product names corrected (fake tier suffixes stripped)
- [x] Deployed: backend on Railway, frontend on Vercel
- [x] README, TECHNICAL, DECISIONS, HANDOFF docs up to date

---

## What's NOT Done

- [ ] **Demo video** — record 3–5 min screen recording on https://shopsense-eight.vercel.app, upload to YouTube unlisted, add link to README
- [ ] **Submit** to hackathon judges

---

## Key File Locations

```
C:\Kasparro\shopsense\
├── backend/
│   ├── main.py                    FastAPI app + /api/chat SSE endpoint
│   ├── start.py                   Windows entry (ProactorEventLoop for Playwright)
│   ├── .env                       GROQ_API_KEY, SHOPIFY_*, GOOGLE_*, ALLOWED_ORIGINS
│   ├── agent/
│   │   ├── shopify_client.py      Admin GraphQL — primary product source
│   │   ├── browser_agent.py       Playwright + Groq Vision — fallback
│   │   ├── confidence_engine.py   Deterministic scoring (zero LLM)
│   │   ├── intent_extractor.py    Groq LLM → structured JSON intent
│   │   ├── followup_generator.py  Follow-up question logic
│   │   └── product_ranker.py      Streaming reasoning + elimination reasons
│   └── scripts/
│       ├── populate_shopify.py    Creates 199 products
│       ├── fix_product_names.py   Strips tier suffixes, deletes duplicates
│       ├── upload_images_ddg.py   DuckDuckGo image uploader (no API key)
│       ├── upload_images_google.py Google image fallback (100/day limit)
│       ├── remove_all_images.py   Bulk image removal
│       ├── remove_bad_images.py   Remove by filename pattern
│       └── list_products.py       Product audit tool
├── frontend/
│   └── components/
│       ├── ChatInterface.tsx      Main chat, SSE consumer, budget chips, reject flow
│       ├── ConfidenceMeter.tsx    Animated ring + breakdown + journey
│       ├── ProductCard.tsx        Card + TTS + Share + Ask + Add to Cart
│       └── EliminationPanel.tsx   Ruled-out products with AI reasons
├── README.md
├── TECHNICAL.md
├── DECISIONS.md  (20 entries)
└── HANDOFF.md    ← this file
```

---

## How to Run Locally

**Backend:**
```cmd
cd C:\Kasparro\shopsense\backend
py start.py
```
Health check: http://localhost:8000/health → `{"status":"ok"}`

**Frontend** (separate terminal):
```cmd
cd C:\Kasparro\shopsense\frontend
npm run dev
```
Open: http://localhost:3000

**Push to GitHub (rebase workflow — friend commits concurrently):**
```cmd
cd C:\Kasparro\shopsense
git stash
git fetch origin && git rebase origin/main
git stash pop
git add <files>
git commit -m "your message"
git push
```

---

## SSE Event Protocol

| Event | Payload | When |
|---|---|---|
| `confidence` | `{score, breakdown}` | After intent + after product search |
| `followup` | `{question}` | score < 80 and followups < 2 |
| `status` | `{text}` | While searching |
| `message` | `{content}` | Agent commentary |
| `budget_pick` | `{product, reasoning, ...}` | Budget optimizer recommendation |
| `recommendation_start` | `{product, elimination}` | Product picked |
| `token` | `{text}` | Reasoning stream chunk |
| `recommendation_done` | `{regret_risk, tradeoff}` | Stream complete |
| `done` | — | Request complete |

---

## Environment Variables (backend/.env)

```env
GROQ_API_KEY=gsk_...
SHOPIFY_STORE_URL=shopsense-rueprzpz.myshopify.com
SHOPIFY_ADMIN_TOKEN=shpat_...
ALLOWED_ORIGINS=http://localhost:3000,https://shopsense-eight.vercel.app
GOOGLE_API_KEY=AIza...          # optional — for upload_images_google.py only
GOOGLE_CX=...                   # optional — Google Custom Search Engine ID
```
