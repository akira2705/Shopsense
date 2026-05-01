import asyncio
import json
import os
import sys
import uuid

# Windows: uvicorn defaults to SelectorEventLoop which can't spawn subprocesses.
# Playwright needs ProactorEventLoop to launch Chromium.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

from agent.confidence_engine import compute_confidence
from agent.followup_generator import generate_followup
from agent.intent_extractor import extract_intent
from agent.product_ranker import rank_and_reason
from agent.browser_agent import search_products_stream, search_products_broad_stream
import agent.shopify_client as shopify_client

app = FastAPI(title="ShopSense API", version="1.0.0")

# CORS — allow Vercel frontend and local dev
_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
_sessions: dict[str, dict] = {}

# Groq client for /api/ask
_groq = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
_LLM = "llama-3.3-70b-versatile"


# ─── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    history: list[dict] = []


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"followup_count": 0, "intent": {}}
    return _sessions[session_id]


def _reset_session(session_id: str) -> None:
    _sessions[session_id] = {"followup_count": 0, "intent": {}}


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Render health check endpoint."""
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    session = _get_session(session_id)

    async def stream():
        try:
            # 1. Extract intent (merge with existing session intent)
            intent = await extract_intent(
                message=req.message,
                history=req.history,
                existing_intent=session.get("intent", {}),
            )
            session["intent"] = intent

            # 2. Compute confidence before searching products
            pre_conf = compute_confidence(intent, [])
            yield _sse({
                "type": "confidence",
                "score": pre_conf["score"],
                "breakdown": pre_conf["breakdown"],
                "session_id": session_id,
            })

            # 3. Decide whether to ask a follow-up
            followup_count = session.get("followup_count", 0)
            if pre_conf["score"] < 80 and followup_count < 2:
                question = await generate_followup(intent, followup_count)
                if question:
                    session["followup_count"] = followup_count + 1
                    _sessions[session_id] = session
                    yield _sse({"type": "followup", "question": question})
                    yield _sse({"type": "done"})
                    return

            # 4. Search products — Shopify store first, live browser as fallback
            products = []

            # 4a. Shopify store search (instant, no browser needed)
            if shopify_client.is_configured():
                yield _sse({"type": "status", "text": "Searching store…"})
                products = await shopify_client.search_products(intent)
                if not products:
                    # Broad Shopify search (no budget filter)
                    products = await shopify_client.search_products_broad(intent)

            # 4b. Browser fallback when Shopify not configured or returned nothing
            if not products:
                async for event in search_products_stream(intent):
                    if event["type"] == "products":
                        products = event["data"]
                    else:
                        yield _sse(event)

            # 4c. Browser broad fallback
            if not products:
                yield _sse({
                    "type": "message",
                    "content": "Hmm, nothing exact — let me widen the search a bit.",
                })
                async for event in search_products_broad_stream(intent):
                    if event["type"] == "products":
                        products = event["data"]
                    else:
                        yield _sse(event)

            # 4d. Still nothing
            if not products:
                category = intent.get("category", "that")
                yield _sse({
                    "type": "message",
                    "content": (
                        f"I couldn't find any matching products for {category} right now. "
                        f"Try rephrasing, or give me a different category and I'll try again."
                    ),
                })
                yield _sse({"type": "done"})
                return

            # 5. Re-score with actual products
            final_conf = compute_confidence(intent, products)
            yield _sse({
                "type": "confidence",
                "score": final_conf["score"],
                "breakdown": final_conf["breakdown"],
            })

            # 6. Commit message
            yield _sse({
                "type": "message",
                "content": (
                    f"I'm {final_conf['score']}% confident in this recommendation. "
                    f"Here's why everything else was ruled out."
                ),
            })

            # 7. Rank + generate reasoning
            # Intercept private fields before forwarding to frontend
            async for event in rank_and_reason(intent, products):
                if event["type"] == "recommendation_start":
                    session["ranked_products"]  = event.pop("_all_ranked", [])
                    session["budget_pick"]       = event.pop("_budget_pick", None)
                    session["top_product"]       = event.pop("_top_product", None)
                    session["pick_index"]        = 0
                    _sessions[session_id]        = session
                    # Send budget_pick as separate event if exists
                    if session["budget_pick"]:
                        yield _sse({"type": "budget_pick", **session["budget_pick"]})
                yield _sse(event)

            # 8. Reset follow-up count for next question
            session["followup_count"] = 0
            _sessions[session_id] = session

        except Exception as exc:
            print(f"[main] stream error: {exc}")
            yield _sse({"type": "error", "message": "Something went wrong. Please try again."})

        finally:
            yield _sse({"type": "done"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/reset")
async def reset(req: ChatRequest):
    """Reset session state (called by 'Start over' button)."""
    if req.session_id:
        _reset_session(req.session_id)
    return {"status": "reset"}


# ─── New feature endpoints ──────────────────────────────────────────────────────

class SessionRequest(BaseModel):
    session_id: str

class AskRequest(BaseModel):
    session_id: str
    question: str


@app.post("/api/next-pick")
async def next_pick(req: SessionRequest):
    """Return the next-best ranked product when user says 'not this one'."""
    session = _get_session(req.session_id)
    ranked  = session.get("ranked_products", [])
    idx     = session.get("pick_index", 0) + 1

    if idx >= len(ranked) or not ranked:
        return JSONResponse({
            "error": True,
            "message": "No more alternatives — try describing your needs differently.",
        })

    session["pick_index"] = idx
    _sessions[req.session_id] = session
    product = ranked[idx - 1]  # ranked list starts at index 1 (top was 0)

    return {
        "product":          product,
        "confidence_score": product.get("_score", 0),
        "pick_number":      idx + 1,
    }


@app.post("/api/ask")
async def ask_product(req: AskRequest):
    """Answer a free-form question about the currently recommended product."""
    session = _get_session(req.session_id)
    top     = session.get("top_product")

    if not top:
        return {"answer": "Ask me something first — search for a product and I'll answer questions about my recommendation."}

    prompt = (
        f"Product: {top.get('title','')}\n"
        f"Price: ₹{top.get('price',0):,.0f}\n"
        f"Rating: {top.get('rating','N/A')}★ from {top.get('review_count','?')} reviews\n"
        f"Tags: {', '.join(top.get('tags', []))}\n"
        f"Description: {top.get('description','')[:600]}\n\n"
        f"User question: {req.question}\n\n"
        f"Answer in 1-3 sentences using only the product info above. "
        f"Be honest if the information isn't available. Don't make up specs."
    )

    try:
        resp = await _groq.chat.completions.create(
            model=_LLM,
            max_tokens=200,
            messages=[
                {"role": "system", "content": "You are a helpful shopping assistant answering questions about a specific product. Be concise and honest."},
                {"role": "user",   "content": prompt},
            ],
        )
        return {"answer": resp.choices[0].message.content.strip()}
    except Exception as exc:
        print(f"[ask] error: {exc}")
        return {"answer": "Sorry, I couldn't fetch an answer right now. Try again."}
