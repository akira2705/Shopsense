import os
import anthropic

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../prompts/followup_prompt.txt")
with open(_PROMPT_PATH) as f:
    _PROMPT_TEMPLATE = f.read()

# Hardcoded fallbacks keyed by missing_info label
_FALLBACKS = {
    "use_case": "Is this for road running, trail, or more casual everyday use?",
    "surface_type": "Will you mostly be running on roads or trails?",
    "budget": "Do you have a budget in mind, or should I show you the best option regardless of price?",
    "skin_type": "What's your skin type — oily, dry, or combination?",
    "skin_concern": "Is there a specific concern you're trying to address — acne, dryness, dullness?",
    "frequency": "How often do you plan to use this?",
    "occasion": "Is this for everyday use or a specific occasion?",
    "recipient": "Who is this for — you, or a gift for someone else?",
}


async def generate_followup(intent: dict, followup_count: int) -> str | None:
    if followup_count >= 2:
        return None

    missing_info = [m for m in intent.get("missing_info", []) if m]
    if not missing_info:
        return None

    top_missing = missing_info[0]

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
        response = await _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        question = response.content[0].text.strip().strip('"\'')
        return question if question else _FALLBACKS.get(top_missing)

    except Exception:
        return _FALLBACKS.get(top_missing, f"Can you tell me more about {top_missing.replace('_', ' ')}?")
