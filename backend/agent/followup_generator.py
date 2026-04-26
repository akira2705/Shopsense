import os

from openai import AsyncOpenAI

_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

_MODEL = "llama-3.3-70b-versatile"

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../prompts/followup_prompt.txt")
with open(_PROMPT_PATH) as f:
    _PROMPT_TEMPLATE = f.read()

# Hardcoded fallbacks keyed by missing_info label
_FALLBACKS = {
    "use_case":      "What'll you mainly use it for?",
    "budget":        "Any budget in mind, or should I find the best regardless of price?",
    "skin_type":     "Oily, dry, or combination skin?",
    "skin_concern":  "Any specific concern — acne, dryness, dark spots?",
    "surface_type":  "Mostly roads or trails?",
    "transmission":  "Manual or automatic — any preference?",
    "fuel_type":     "Petrol, diesel, or open to CNG/electric?",
    "brand":         "Any brand in mind, or totally open?",
    "priorities":    "What's the one thing that matters most to you?",
    "frequency":     "How often will you use it?",
    "occasion":      "Everyday use or a specific occasion?",
    "recipient":     "Is this for you or a gift for someone?",
    "condition":     "New or would you consider second-hand?",
}

# Priority order — highest confidence impact first
# use_case = 25 pts, budget = 20 pts, everything else = ~15 pts
_PRIORITY_ORDER = [
    "use_case",
    "budget",
    "skin_type",
    "skin_concern",
    "surface_type",
    "transmission",
    "fuel_type",
    "brand",
    "priorities",
    "frequency",
    "occasion",
    "recipient",
    "condition",
]


def _pick_best_missing(missing_info: list[str]) -> str:
    """Pick the highest-impact missing field to ask about."""
    for priority_field in _PRIORITY_ORDER:
        for m in missing_info:
            if priority_field in m.lower() or m.lower() in priority_field:
                return m
    # Fallback: just take first
    return missing_info[0]


async def generate_followup(intent: dict, followup_count: int) -> str | None:
    if followup_count >= 2:
        return None

    missing_info = [m for m in intent.get("missing_info", []) if m]
    if not missing_info:
        return None

    # Pick highest-impact missing field, not just first in list
    top_missing = _pick_best_missing(missing_info)

    known = {
        k: v for k, v in intent.items()
        if v and k not in ("missing_info",) and v != [] and v != {}
    }

    prompt = _PROMPT_TEMPLATE.format(
        missing=top_missing,
        known=str(known),
        followup_count=followup_count,
    )

    try:
        response = await _client.chat.completions.create(
            model=_MODEL,
            max_tokens=120,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a sharp, friendly shopping assistant. "
                        "Ask one short natural clarifying question. "
                        "Sound like a smart friend texting, not a form field. "
                        "Return ONLY the question text, no quotes, no explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        question = response.choices[0].message.content.strip().strip('"\'')
        return question if question else _FALLBACKS.get(top_missing)

    except Exception:
        return _FALLBACKS.get(top_missing, f"Can you tell me more about {top_missing.replace('_', ' ')}?")
