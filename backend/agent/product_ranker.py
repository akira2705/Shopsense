"""
Product Ranker

A. Streams reasoning tokens live via Groq streaming API
B. AI-generated elimination reasons (single batched LLM call)
C. Shared client across all calls (Groq via OpenAI-compatible endpoint)
"""

import json
import os
import re
from typing import AsyncGenerator

from openai import AsyncOpenAI

from agent.confidence_engine import compute_confidence

_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

_MODEL = "llama-3.3-70b-versatile"

_REASONING_SYSTEM = (
    "You are a shopping assistant helping a user make a confident, regret-free purchase. "
    "Write concise, honest reasoning for why a specific product is the right choice. "
    "Never use filler phrases like 'Certainly', 'Great choice', 'Perfect for you', 'This product'. "
    "Sound like a knowledgeable friend, not a product listing."
)

_ELIMINATION_SYSTEM = (
    "You are a shopping assistant. Given a user's shopping intent and a list of products that were NOT "
    "chosen as the best match, explain in one short honest sentence (max 10 words) why each wasn't selected. "
    "Be specific — mention price, use case mismatch, or feature gaps. Never say 'Lower overall match score'."
)

_REGRET_SYSTEM = "You assess purchase regret risk. Return only valid JSON, no extra text."


async def rank_and_reason(intent: dict, products: list[dict]) -> AsyncGenerator[dict, None]:
    """Async generator yielding SSE event dicts."""

    if not products:
        yield {"type": "error", "message": "No products to rank."}
        return

    # Pre-filter: remove products that hard-violate explicit constraints
    # e.g. user said "8 seater" → eliminate clear 5-seaters before scoring
    filtered = _apply_constraint_filter(intent, products)
    # If the filter removed everything, fall back to the full list
    if filtered:
        products = filtered

    # Score every product deterministically
    scored = []
    for p in products:
        conf = compute_confidence(intent, [p])
        scored.append({**p, "_score": conf["score"]})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    top = scored[0]

    # B: AI elimination reasons — single batched call
    elimination = await _ai_elimination_reasons(intent, scored[1:])

    # Emit recommendation_start with product info + elimination (reasoning streams after)
    # IMPORTANT: preserve source, rating, review_count, url — used by ProductCard
    yield {
        "type": "recommendation_start",
        "product": {
            "id": top["id"],
            "title": top["title"],
            "price": top["price"],
            "image_url": top.get("image_url"),
            "variant_id": top.get("variant_id"),
            "tags": top.get("tags", []),
            "source": top.get("source"),          # "amazon"|"flipkart"|"carwale"|"olx"
            "rating": top.get("rating"),
            "review_count": top.get("review_count"),
            "url": top.get("url"),                # direct product URL
        },
        "confidence_score": top["_score"],
        "elimination": elimination,
    }

    # A: Stream reasoning tokens live
    reasoning_text = ""
    _budget = ("₹" + f"{intent['budget_max']:,}") if intent.get("budget_max") else "not specified"
    reasoning_user_prompt = (
        f"Product: {top['title']}\n"
        f"Price: ₹{top['price']:,.0f}\n"
        f"Description: {top.get('description', '')[:400]}\n"
        f"Tags: {', '.join(top.get('tags', []))}\n\n"
        f"User:\n"
        f"- Budget: {_budget}\n"
        f"- Use case: {intent.get('use_case') or 'general use'}\n"
        f"- Priorities: {', '.join(intent.get('priorities', [])) or 'not specified'}\n"
        f"- Constraints: {', '.join(intent.get('constraints', [])) or 'none'}\n\n"
        f"Write 2-3 sentences explaining why this product fits this user. "
        f"Mention their actual use case and constraints by name. Be direct and honest."
    )

    try:
        stream = await _client.chat.completions.create(
            model=_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": _REASONING_SYSTEM},
                {"role": "user", "content": reasoning_user_prompt},
            ],
            stream=True,
        )
        async for chunk in stream:
            text = chunk.choices[0].delta.content or ""
            if text:
                reasoning_text += text
                yield {"type": "token", "text": text}

    except Exception as exc:
        print(f"[product_ranker] streaming error: {exc}")
        reasoning_text = (
            f"{top['title']} matches your stated needs based on category, budget, and use case alignment."
        )
        yield {"type": "token", "text": reasoning_text}

    # Get regret_risk / tradeoff — fast non-streaming call
    regret_risk = "low"
    regret_scenario = ""
    tradeoff = ""

    structured_prompt = (
        f"Product: {top['title']} (₹{top['price']:,.0f})\n"
        f"User use case: {intent.get('use_case') or 'general use'}\n"
        f"User constraints: {', '.join(intent.get('constraints', [])) or 'none'}\n\n"
        f"Return ONLY valid JSON:\n"
        f'{{"regret_risk": "<low|medium|high>", '
        f'"regret_scenario": "one specific realistic scenario", '
        f'"tradeoff": "main tradeoff in one sentence"}}'
    )

    try:
        resp = await _client.chat.completions.create(
            model=_MODEL,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _REGRET_SYSTEM},
                {"role": "user", "content": structured_prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            regret_risk = parsed.get("regret_risk", "low")
            regret_scenario = parsed.get("regret_scenario", "")
            tradeoff = parsed.get("tradeoff", "")
    except Exception as exc:
        print(f"[product_ranker] regret error: {exc}")

    yield {
        "type": "recommendation_done",
        "reasoning": reasoning_text,
        "regret_risk": regret_risk,
        "regret_scenario": regret_scenario,
        "tradeoff": tradeoff,
    }


async def _ai_elimination_reasons(intent: dict, products: list[dict]) -> list[dict]:
    """Single LLM call to explain why each non-top product wasn't chosen."""
    if not products:
        return []

    products_to_explain = products[:12]

    product_list = "\n".join(
        f"{i+1}. {p['title']} (₹{p['price']:,.0f}) — tags: {', '.join(p.get('tags', []))}"
        for i, p in enumerate(products_to_explain)
    )

    _budget = ("₹" + f"{intent['budget_max']:,}") if intent.get("budget_max") else "not specified"
    prompt = (
        f"User wants: {intent.get('category', 'a product')} "
        f"for {intent.get('use_case', 'general use')}.\n"
        f"Budget: {_budget}.\n"
        f"Constraints: {', '.join(intent.get('constraints', [])) or 'none'}.\n\n"
        f"These products were NOT chosen as the best match. "
        f"For each, write one short sentence (max 10 words) why:\n\n"
        f"{product_list}\n\n"
        f"Return ONLY a JSON array:\n"
        f'[{{"title": "exact product name", "reason": "short reason"}}, ...]'
    )

    try:
        resp = await _client.chat.completions.create(
            model=_MODEL,
            max_tokens=600,
            messages=[
                {"role": "system", "content": _ELIMINATION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            price_map = {p["title"]: p["price"] for p in products_to_explain}
            return [
                {
                    "title": item.get("title", ""),
                    "price": price_map.get(item.get("title", ""), 0),
                    "reason": item.get("reason", "Lower match score"),
                }
                for item in parsed
                if item.get("title")
            ]
    except Exception as exc:
        print(f"[product_ranker] ai_elimination error: {exc}")

    # Fallback to deterministic
    return _build_elimination_deterministic(intent, products_to_explain)


def _build_elimination_deterministic(intent: dict, products: list[dict]) -> list[dict]:
    budget_max = intent.get("budget_max")
    use_case = (intent.get("use_case") or "").lower()
    constraints = [c.lower() for c in intent.get("constraints", [])]
    return [
        {
            "title": p["title"],
            "price": p["price"],
            "reason": _reason_for_elimination(p, budget_max, use_case, constraints),
        }
        for p in products
    ]


def _apply_constraint_filter(intent: dict, products: list) -> list:
    """
    Remove products that clearly violate hard constraints before scoring.
    Uses the same _constraint_violated logic as the confidence engine.
    If filtering removes ALL products, returns [] so caller falls back to full list.
    """
    from agent.confidence_engine import _constraint_violated

    constraints = [c.lower().strip() for c in intent.get("constraints", []) if c]
    if not constraints:
        return products

    result = list(products)

    for c in constraints:
        filtered = [p for p in result if not _constraint_violated(c, p)]
        # Only apply if it narrows without emptying
        if filtered:
            result = filtered

    return result


def _reason_for_elimination(product: dict, budget_max, use_case: str, constraints: list) -> str:
    price = product.get("price", 0)
    tags_str = " ".join(product.get("tags", [])).lower()
    desc = product.get("description", "").lower()

    if budget_max and price > budget_max:
        return f"Over budget (₹{price:,.0f})"

    for constraint in constraints:
        if "flat feet" in constraint:
            if any(t in tags_str for t in ["minimalist", "barefoot", "zero-drop", "zero drop"]):
                return "Minimalist design — unsuitable for flat feet"
        if "road" in constraint:
            if "trail" in tags_str and "road" not in tags_str:
                return "Trail-specific — not optimised for road running"
        if "trail" in constraint:
            if "road" in tags_str and "trail" not in tags_str:
                return "Road shoe — not suitable for trails"

    if use_case:
        use_case_words = [w for w in use_case.split() if len(w) > 3]
        if use_case_words and not any(w in tags_str or w in desc for w in use_case_words):
            return "Use case mismatch"

    return "Lower overall match score"
