"""
MARKETPLACE_SAFETY/description_moderation.py — Product Description Moderation
"""
import re

SPAM_PATTERNS = [
    r"(?:whatsapp|telegram|phone)[\s:]+[\+\d\s\-]{7,}",  # contact numbers
    r"[\w\.-]+@[\w\.-]+\.\w+",                             # email addresses
    r"(?:https?://|www\.)\S+",                              # external URLs
    r"(?:call|contact|order).{0,20}(?:directly|outside)",  # bypass attempts
    r"(?:cod|cash).{0,20}(?:home delivery|doorstep)",       # unauthorized COD claims
]

QUALITY_REQUIREMENTS = {
    "min_length":        50,
    "min_sentences":     2,
    "min_unique_words":  8,
}


def moderate_description(description: str) -> dict:
    issues = []

    # Length check
    if len(description) < QUALITY_REQUIREMENTS["min_length"]:
        issues.append({"type": "too_short", "severity": "warning",
                        "message": f"Description too short (min {QUALITY_REQUIREMENTS['min_length']} chars)"})

    # Spam patterns
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, description, re.IGNORECASE):
            issues.append({"type": "spam_pattern", "severity": "high",
                            "message": "Contains contact info or external links (not allowed)"})
            break

    # Keyword stuffing (repeated words)
    words  = description.lower().split()
    unique = len(set(words))
    if len(words) > 20 and unique / len(words) < 0.4:
        issues.append({"type": "keyword_stuffing", "severity": "medium",
                        "message": "Description appears to have excessive repetition"})

    # Sentence structure
    sentences = [s.strip() for s in re.split(r"[.!?]", description) if len(s.strip()) > 5]
    if len(sentences) < QUALITY_REQUIREMENTS["min_sentences"]:
        issues.append({"type": "poor_structure", "severity": "warning",
                        "message": "Description should have at least 2 complete sentences"})

    approved = not any(i["severity"] == "high" for i in issues)
    return {"approved": approved, "issues": issues, "quality_score": _score(description, issues)}


def _score(text: str, issues: list) -> int:
    score = 100
    score -= len(text) < 100 and 20 or 0
    score -= len(text) < 50  and 30 or 0
    score -= sum(20 if i["severity"] == "high" else 10 for i in issues)
    return max(0, score)
