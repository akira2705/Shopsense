"""
Confidence Engine — fully deterministic, zero LLM calls.

Scoring per product:
  Category match:     0–25 pts  (product type matches stated need)
  Budget match:       0–20 pts  (price within budget)
  Use case match:     0–25 pts  (description/tags match use case)
  Priority match:     0–15 pts  (PROPORTIONAL — each priority checked individually)
  Ambiguity penalty:  −8 pts    per unresolved missing_info item
  Constraint penalty: −15 pts   per hard constraint clearly violated

Key fixes vs. naive approach:
  - Short tech terms (RAM, GPU, SSD, 4K, AC) are NOT filtered out
  - Priority scoring is per-priority, not all-or-nothing
  - Tech synonyms expand matches: GPU → nvidia/rtx/radeon/graphics card
  - Seating constraints use positive inclusion, not just negative exclusion

Commit threshold: ≥ 80 pts
"""


# ── Tech term synonym expansions ─────────────────────────────────────────────
# When user says "GPU", also match "nvidia", "rtx", "gtx", "radeon", "graphics card"
# This means a Lenovo with "NVIDIA RTX 4060" matches "GPU" even without the word "GPU"

_SYNONYMS: dict[str, list[str]] = {
    # Graphics
    "gpu":             ["gpu", "nvidia", "rtx", "gtx", "radeon", "graphics card", "dedicated graphics", "discrete gpu"],
    "graphics":        ["graphics", "nvidia", "rtx", "gtx", "radeon", "gpu", "dedicated"],
    "graphics card":   ["graphics card", "nvidia", "rtx", "gtx", "radeon", "gpu", "dedicated graphics"],

    # Memory
    "ram":             ["ram", "memory", "8gb", "16gb", "32gb", "ddr4", "ddr5", "lpddr"],
    "memory":          ["memory", "ram", "8gb", "16gb", "32gb", "ddr4", "ddr5"],

    # Storage
    "ssd":             ["ssd", "nvme", "512gb", "1tb", "solid state"],
    "storage":         ["storage", "ssd", "hdd", "nvme", "512gb", "1tb"],

    # Display / screen
    "screen":          ["screen", "display", "oled", "amoled", "ips", "led", "4k", "1080p", "1440p", "144hz", "120hz", "panel"],
    "screen quality":  ["oled", "amoled", "ips", "4k", "1080p", "1440p", "144hz", "120hz", "display", "retina"],
    "display":         ["display", "screen", "oled", "amoled", "ips", "4k", "1080p", "144hz"],
    "resolution":      ["4k", "1080p", "1440p", "2k", "fhd", "qhd", "uhd", "retina"],

    # Battery
    "battery":         ["battery", "mah", "5000mah", "6000mah", "wh", "battery life", "endurance"],
    "battery life":    ["battery", "mah", "5000mah", "6000mah", "all day", "long battery"],

    # Camera
    "camera":          ["camera", "mp", "megapixel", "108mp", "50mp", "lens", "photography"],

    # Connectivity
    "5g":              ["5g"],
    "wifi":            ["wifi", "wi-fi", "wireless"],

    # Vehicle specifics
    "fuel efficiency": ["kmpl", "km/kg", "mileage", "fuel efficient", "efficiency", "economy"],
    "mileage":         ["mileage", "kmpl", "km/kg", "fuel efficient"],
    "safety":          ["safety", "airbag", "ncap", "abs", "adas", "rated"],
    "sunroof":         ["sunroof", "moonroof", "panoramic"],
    "automatic":       ["automatic", "cvt", "at", "imt", "dct", "auto"],

    # Seating (for constraints)
    "7 seater":        ["7 seater", "7-seater", "mpv", "muv", "seven seater"],
    "8 seater":        ["8 seater", "8-seater", "mpv", "muv", "eight seater"],
    "7-seater":        ["7 seater", "7-seater", "mpv", "muv"],
    "8-seater":        ["8 seater", "8-seater", "mpv", "muv"],
    "seating for 7":   ["7 seater", "7-seater", "mpv", "muv"],
    "seating for 8":   ["8 seater", "8-seater", "mpv", "muv"],
}

# Tags that mark a product as clearly NOT an 8-seater vehicle
_SMALL_VEHICLE_TAGS = {"hatchback", "city car", "micro", "alto", "swift", "i20", "scooter", "activa", "bike", "motorcycle"}
_SEATING_TAGS       = {"7 seater", "7-seater", "8 seater", "8-seater", "mpv", "muv", "innova", "ertiga", "carens", "fortuner", "hycross"}


def _text(product: dict) -> str:
    return " ".join([
        product.get("title", ""),
        " ".join(product.get("tags", [])),
        product.get("description", ""),
    ]).lower()


def _expand(term: str) -> list[str]:
    """Return term plus any synonym expansions."""
    t = term.lower().strip()
    return _SYNONYMS.get(t, [t])


def _phrase_in_text(phrase: str, text: str) -> bool:
    """Check if a phrase (or its synonyms) appears in product text."""
    # Direct match first
    if phrase in text:
        return True
    # Try synonyms
    for syn in _expand(phrase):
        if syn in text:
            return True
    # Try individual words from the phrase (min 2 chars, catches RAM/SSD/4K)
    words = [w for w in phrase.split() if len(w) >= 2]
    for w in words:
        for syn in _expand(w):
            if syn in text:
                return True
    return False


def _priority_score_for_product(priorities: list[str], product: dict) -> tuple[int, int]:
    """
    Returns (points_earned, points_possible) for this product against the priorities list.
    Each priority is evaluated independently — partial credit per priority.
    """
    if not priorities:
        return 0, 0

    text = _text(product)
    matched = sum(1 for p in priorities if _phrase_in_text(p, text))
    return matched, len(priorities)


def _constraint_violated(constraint: str, product: dict) -> bool:
    """Return True if this product clearly violates the constraint."""
    c = constraint.lower().strip()
    text = _text(product)

    # Seating capacity
    for seating_key in ["8 seater", "seating for 8", "8-seater"]:
        if seating_key in c:
            has_seating_tag = any(t in text for t in _SEATING_TAGS)
            is_small = any(t in text for t in _SMALL_VEHICLE_TAGS)
            return is_small and not has_seating_tag

    for seating_key in ["7 seater", "seating for 7", "7-seater"]:
        if seating_key in c:
            has_seating_tag = any(t in text for t in _SEATING_TAGS)
            is_small = any(t in text for t in _SMALL_VEHICLE_TAGS)
            return is_small and not has_seating_tag

    # Body type
    if "suv" in c:
        is_not_suv = any(t in text for t in ["hatchback", "sedan", "scooter", "bike", "motorcycle"])
        is_suv = any(t in text for t in ["suv", "crossover", "xuv", "creta", "nexon", "fortuner"])
        return is_not_suv and not is_suv

    # Fuel type
    for fuel in ["petrol", "diesel", "cng", "electric", "hybrid"]:
        if fuel in c and fuel in text:
            return False  # matches, not violated
        if fuel in c:
            other_fuels = {"petrol", "diesel", "cng"} - {fuel}
            return any(f in text for f in other_fuels) and fuel not in text

    # Automatic transmission
    if c in ("automatic", "automatic transmission", "auto"):
        is_manual = ("manual" in text or " mt " in text or "6mt" in text or "5mt" in text)
        is_auto = ("automatic" in text or "cvt" in text or " at " in text)
        return is_manual and not is_auto

    return False


def compute_confidence(intent: dict, products: list) -> dict:
    scores = {
        "category":          0,
        "budget":            0,
        "use_case":          0,
        "priorities":        0,
        "ambiguity_penalty": 0,
    }

    # ── Category (0–25) ───────────────────────────────────────────────────────
    category = (intent.get("category") or "").lower().strip()
    cat_words = [w for w in category.split() if len(w) >= 2]
    if cat_words and products:
        matched = sum(1 for p in products if any(_phrase_in_text(w, _text(p)) for w in cat_words))
        scores["category"] = int(25 * matched / len(products))
    elif cat_words:
        scores["category"] = 15

    # ── Budget (0–20) ─────────────────────────────────────────────────────────
    budget_max = intent.get("budget_max")
    if budget_max:
        if products:
            within = sum(1 for p in products if p.get("price", float("inf")) <= budget_max)
            scores["budget"] = int(20 * within / len(products))
        else:
            scores["budget"] = 15
    else:
        scores["budget"] = 5

    # ── Use case (0–25) ───────────────────────────────────────────────────────
    use_case = (intent.get("use_case") or "").lower().strip()
    uc_words = [w for w in use_case.split() if len(w) >= 3]
    if uc_words and products:
        matched = sum(1 for p in products if any(_phrase_in_text(w, _text(p)) for w in uc_words))
        scores["use_case"] = int(25 * matched / len(products))
    elif uc_words:
        scores["use_case"] = 18

    # ── Priorities (0–15) — PER-PRIORITY proportional scoring ────────────────
    # Each priority (e.g. "screen quality", "graphics card", "RAM") is evaluated
    # independently. Partial credit: 2 of 3 priorities matched → 10/15 points.
    priorities = [p.lower().strip() for p in intent.get("priorities", []) if p]
    if priorities and products:
        total_earned = 0
        total_possible = 0
        for p in products:
            earned, possible = _priority_score_for_product(priorities, p)
            total_earned   += earned
            total_possible += possible
        if total_possible > 0:
            scores["priorities"] = int(15 * total_earned / total_possible)
    elif priorities:
        scores["priorities"] = 10

    # ── Ambiguity + constraint penalty ───────────────────────────────────────
    missing = [m for m in intent.get("missing_info", []) if m]
    ambiguity_penalty = -(len(missing) * 8)

    # Hard constraint violation: if none of the products meet the constraint → −15
    constraints = [c for c in intent.get("constraints", []) if c]
    constraint_penalty = 0
    for c in constraints:
        if products:
            any_product_meets = any(not _constraint_violated(c, p) for p in products)
            if not any_product_meets:
                constraint_penalty -= 15

    scores["ambiguity_penalty"] = ambiguity_penalty + constraint_penalty

    total = max(0, min(100, sum(scores.values())))

    return {
        "score": total,
        "breakdown": scores,
        "ambiguity_count": len(missing),
    }
