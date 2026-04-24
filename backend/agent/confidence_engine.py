"""
Confidence Engine - fully deterministic, zero LLM calls.

Formula:
  Category match:    0-25 pts
  Budget match:      0-20 pts
  Use case match:    0-25 pts
  Priority match:    0-15 pts
  Ambiguity penalty: -8 pts per unresolved missing_info item

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

    # --- Ambiguity penalty (-8 per item) ---
    missing = [m for m in intent.get("missing_info", []) if m]
    scores["ambiguity_penalty"] = -(len(missing) * 8)

    total = max(0, min(100, sum(scores.values())))

    return {
        "score": total,
        "breakdown": scores,
        "ambiguity_count": len(missing),
    }
