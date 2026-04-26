# ShopSense — Frontend

Next.js 15 frontend for ShopSense. Chat interface with animated confidence ring, live browser status stream, and token-by-token reasoning display.

## Stack

- **Next.js 15** (App Router)
- **TypeScript**
- **Tailwind CSS v4**
- **Framer Motion** — confidence ring, status transitions, message animations
- **Lucide React** — icons

## Key Components

| File | What it does |
|---|---|
| `components/ChatInterface.tsx` | Main chat UI — SSE client, voice input, quick-start chips, live status |
| `components/ConfidenceMeter.tsx` | Animated SVG ring + score breakdown + confidence journey |
| `components/ProductCard.tsx` | Recommendation card — source badge, rating, streaming reasoning |
| `components/EliminationPanel.tsx` | Collapsible list of ruled-out products with AI reasons |
| `lib/api.ts` | Typed SSE streaming client, all event types |

## Local Dev

```bash
npm install
npm run dev
```

Requires the backend running at `http://localhost:8000`. See the [main README](../README.md).

## Environment

```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production, set `NEXT_PUBLIC_API_URL` to your Render backend URL in Vercel's environment settings.
