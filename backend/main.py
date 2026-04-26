import json
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agent.confidence_engine import compute_confidence
from agent.followup_generator import generate_followup
from agent.intent_extractor import extract_intent
from agent.product_ranker import rank_and_reason
from agent.browser_agent import search_products, search_products_broad

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

# In-memory session store {session_id: {followup_count, intent}}
_sessions: dict[str, dict] = {}


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

            # 4. Search Shopify
            products = await search_products(intent)

            # 4a. Fallback: broad search if nothing matched
            if not products:
                yield _sse({
                    "type": "message",
                    "content": "I couldn't find an exact match — let me broaden the search.",
                })
                products = await search_products_broad(intent)

            # 4b. Still nothing
            if not products:
                yield _sse({
                    "type": "message",
                    "content": "I wasn't able to find products matching your criteria right now. Try adjusting your budget or category.",
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
            async for event in rank_and_reason(intent, products):
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
