"""
Confidence Engine - fully deterministic, zero LLM calls.

Formula:
  Category match:    0-25 pts
  Budget match:      0-20 pts
  Use case match:    0-25 pts
  Priority match:    0-15 pts
  Constraint match:  0-15 pts  (bonus if product meets hard constraints)
  Ambiguity penalty: -8 pts per unresolved missing_info item
  Constraint penalty:-12 pts per hard constraint clearly violated by product pool

Threshold to commit: 80 pts
"""


def _text(product: dict) -> str:
    """Flatten all searchable product text into one lowercase string."""
    return " ".join([
        product.get("title", ""),
        " ".join(product.get("tags", [])),
        product.get("description", ""),
    ]).lower()


def _word_match_ratio(words: list, products: list) -> float:
    """Return fraction of products that contain at least one of the given words."""
    if not products or not words:
        return 0.0
    matched = sum(1 for p in products if any(w in _text(p) for w in words))
    return matched / len(products)


# Seating constraint keywords — for hard seating-capacity checks
_SEATING_KEYWORDS = {
    "8 seater": ["8 seater", "8-seater", "eight seater", "mpv", "muv"],
    "7 seater": ["7 seater", "7-seater", "seven seater", "mpv", "muv", "innova", "ertiga", "carens"],
    "6 seater": ["6 seater", "6-seater", "six seater"],
    "5 seater": ["5 seater", "5-seater", "five seater"],
    "seating for 8": ["8 seater", "8-seater", "mpv", "muv"],
    "seating for 7": ["7 seater", "7-seater", "mpv", "muv"],
}


def _constraint_words(constraint: str) -> list[str]:
    """Extract searchable keywords from a constraint string."""
    c = constraint.lower().strip()
    # Check seating keywords first
    for key, expansions in _SEATING_KEYWORDS.items():
        if key in c:
            return expansions
    # For other constraints, just use words > 3 chars
    return [w for w in c.split() if len(w) > 3]


def compute_confidence(intent: dict, products: list) -> dict:
    scores = {
        "category": 0,
        "budget": 0,
        "use_case": 0,
        "priorities": 0,
        "ambiguity_penalty": 0,
    }

    # --- Category (0-25) ---
    category = (intent.get("category") or "").lower().strip()
    cat_words = [w for w in category.split() if len(w) > 2]
    if cat_words:
        if products:
            scores["category"] = int(25 * _word_match_ratio(cat_words, products))
        else:
            scores["category"] = 15

    # --- Budget (0-20) ---
    budget_max = intent.get("budget_max")
    if budget_max:
        if products:
            within = sum(1 for p in products if p.get("price", float("inf")) <= budget_max)
            scores["budget"] = int(20 * within / len(products))
        else:
            scores["budget"] = 15
    else:
        scores["budget"] = 5

    # --- Use case (0-25) ---
    use_case = (intent.get("use_case") or "").lower().strip()
    uc_words = [w for w in use_case.split() if len(w) > 3]
    if uc_words:
        if products:
            scores["use_case"] = int(25 * _word_match_ratio(uc_words, products))
        else:
            scores["use_case"] = 18

    # --- Priorities (0-15) ---
    priorities = [p.lower() for p in intent.get("priorities", []) if p]
    pri_words = [w for p in priorities for w in p.split() if len(w) > 3]
    if pri_words:
        if products:
            scores["priorities"] = int(15 * _word_match_ratio(pri_words, products))
        else:
            scores["priorities"] = 10

    # --- Constraints — check hard requirements (affects ambiguity penalty) ---
    # Each violated constraint adds an extra penalty on top of the ambiguity penalty
    constraints = [c for c in intent.get("constraints", []) if c]
    constraint_penalty = 0
    for c in constraints:
        c_words = _constraint_words(c)
        if c_words and products:
            # If NONE of the products in the pool match this constraint,
            # it means we likely haven't found what the user needs yet
            ratio = _word_match_ratio(c_words, products)
            if ratio == 0:
                constraint_penalty -= 12  # hard miss — nothing in pool meets this

    scores["ambiguity_penalty"] = -(len([m for m in intent.get("missing_info", []) if m]) * 8) + constraint_penalty

    total = max(0, min(100, sum(scores.values())))

    return {
        "score": total,
        "breakdown": scores,
        "ambiguity_count": len([m for m in intent.get("missing_info", []) if m]),
    }
