import json
import os
import re
import anthropic

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../prompts/intent_prompt.txt")
with open(_PROMPT_PATH) as f:
    _PROMPT_TEMPLATE = f.read()


async def extract_intent(message: str, history: list[dict], existing_intent: dict = {}) -> dict:
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-6:]
    ) or "none"

    existing_text = json.dumps(existing_intent) if existing_intent else "none"

    prompt = _PROMPT_TEMPLATE.format(
        message=message,
        history=history_text,
        existing_intent=existing_text,
    )

    try:
        response = await _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Extract JSON block robustly
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return _keyword_fallback(message, existing_intent)

        parsed = json.loads(match.group())

        # Merge: new non-empty values override existing
        merged = dict(existing_intent)
        for k, v in parsed.items():
            if v is not None and v != "" and v != []:
                merged[k] = v

        return merged

    except (json.JSONDecodeError, anthropic.APIError, Exception):
        return _keyword_fallback(message, existing_intent)


def _keyword_fallback(message: str, existing: dict) -> dict:
    """Regex-based fallback when LLM fails."""
    intent = dict(existing)
    msg = message.lower()

    # Budget
    budget_match = re.search(r"(?:rs\.?|₹)\s*(\d[\d,]*)|(\d[\d,]*)\s*(?:rs\.?|rupees)", msg)
    if budget_match:
        raw_num = (budget_match.group(1) or budget_match.group(2) or "").replace(",", "")
        if raw_num.isdigit():
            intent["budget_max"] = int(raw_num)

    # Constraints
    constraints = list(intent.get("constraints", []))
    if "flat feet" in msg or "flat foot" in msg:
        if "flat feet support" not in constraints:
            constraints.append("flat feet support")
    intent["constraints"] = constraints

    # Use case keywords
    use_case_map = {
        "road running": ["road running", "road run"],
        "trail running": ["trail running", "trail run", "trail"],
        "gym": ["gym", "workout", "training", "exercise"],
        "casual": ["casual", "everyday", "walking"],
        "oily skin": ["oily skin", "oily"],
        "dry skin": ["dry skin", "dry"],
    }
    for use_case, keywords in use_case_map.items():
        if any(kw in msg for kw in keywords):
            intent["use_case"] = use_case
            break

    # Category
    category_map = {
        "running shoes": ["running shoe", "running shoes", "shoes for running"],
        "skincare": ["skincare", "skin care", "moisturizer", "serum", "cleanser"],
        "sneakers": ["sneakers", "trainers"],
    }
    if not intent.get("category"):
        for cat, keywords in category_map.items():
            if any(kw in msg for kw in keywords):
                intent["category"] = cat
                break

    # Default missing info
    if not intent.get("missing_info"):
        missing = []
        if not intent.get("use_case"):
            missing.append("use_case")
        if not intent.get("budget_max"):
            missing.append("budget")
        intent["missing_info"] = missing

    return intent
