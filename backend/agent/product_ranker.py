"""
Product Ranker

Ranks products deterministically by confidence score,
then calls LLM once to generate reasoning for the top product.
Elimination reasons are fully deterministic — no LLM.
"""

import json
import os
import re
from typing import AsyncGenerator

import anthropic

from agent.confidence_engine import compute_confidence

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../prompts/reasoning_prompt.txt")
with open(_PROMPT_PATH) as f:
    _REASONING_TEMPLATE = f.read()


async def rank_and_reason(intent: dict, products: list[dict]) -> AsyncGenerator[dict, None]:
    """Async generator yielding SSE event dicts."""

    if not products:
        yield {"type": "error", "message": "No products to rank."}
        return

    # Score every product deterministically
    scored = []
    for p in products:
        conf = compute_confidence(intent, [p])
        scored.append({**p, "_score": conf["score"]})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    top = scored[0]

    # Build elimination list (deterministic)
    elimination = _build_elimination(intent, scored[1:])

    # Generate reasoning via LLM (single call, structured JSON output)
    prompt = _REASONING_TEMPLATE.format(
        product_name=top["title"],
        product_description=top["description"][:600],
        product_price=f"{top['price']:,.0f}",
        product_tags=", ".join(top.get("tags", [])),
        user_budget=f"₹{intent['budget_max']:,}" if intent.get("budget_max") else "not specified",
        user_use_case=intent.get("use_case") or "general use",
        user_priorities=", ".join(intent.get("priorities", [])) or "not specified",
        user_constraints=", ".join(intent.get("constraints", [])) or "none",
    )

    reasoning = ""
    regret_risk = "low"
    regret_scenario = ""
    tradeoff = ""

    try:
        response = await _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Extract JSON robustly
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            reasoning = parsed.get("reasoning", "")
            regret_risk = parsed.get("regret_risk", "low")
            regret_scenario = parsed.get("regret_scenario", "")
            tradeoff = parsed.get("tradeoff", "")
        else:
            reasoning = raw

    except (json.JSONDecodeError, anthropic.APIError, Exception) as exc:
        print(f"[product_ranker] reasoning error: {exc}")
        reasoning = f"{top['title']} matches your stated needs based on category, budget, and use case alignment."
        tradeoff = "Unable to generate detailed tradeoff analysis."

    yield {
        "type": "recommendation",
        "product": {
            "id": top["id"],
            "title": top["title"],
            "price": top["price"],
            "image_url": top.get("image_url"),
            "variant_id": top.get("variant_id"),
            "tags": top.get("tags", []),
        },
        "reasoning": reasoning,
        "regret_risk": regret_risk,
        "regret_scenario": regret_scenario,
        "tradeoff": tradeoff,
        "confidence_score": top["_score"],
        "elimination": elimination,
    }


def _build_elimination(intent: dict, products: list[dict]) -> list[dict]:
    """
    Deterministically explain why each product was not the top pick.
    No LLM involved — derived purely from confidence sub-scores.
    """
    budget_max = intent.get("budget_max")
    use_case = (intent.get("use_case") or "").lower()
    constraints = [c.lower() for c in intent.get("constraints", [])]

    result = []
    for p in products[:24]:
        reason = _reason_for_elimination(p, budget_max, use_case, constraints)
        result.append({
            "title": p["title"],
            "price": p["price"],
            "reason": reason,
        })

    return result


def _reason_for_elimination(product: dict, budget_max, use_case: str, constraints: list) -> str:
    price = product.get("price", 0)
    tags_str = " ".join(product.get("tags", [])).lower()
    desc = product.get("description", "").lower()

    # 1. Budget check (most objective)
    if budget_max and price > budget_max:
        return f"Over budget (₹{price:,.0f})"

    # 2. Constraint violations
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

    # 3. Use case mismatch
    if use_case:
        use_case_words = [w for w in use_case.split() if len(w) > 3]
        if use_case_words:
            match = any(w in tags_str or w in desc for w in use_case_words)
            if not match:
                return "Use case mismatch"

    # 4. Default: lower confidence score
    return "Lower overall match score"
