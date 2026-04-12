"""AD_QUALITY/ad_content_filter.py — Ad content policy filter."""
BLOCKED_KEYWORDS = [
    "casino", "gambling", "adult", "xxx", "porn", "nude", "drugs",
    "hack", "crack", "weapons", "violence", "racism", "hate",
]

ALLOWED_CATEGORIES = [
    "app_install", "gaming", "finance", "education", "health",
    "travel", "food", "fashion", "tech", "sports", "entertainment",
]


class AdContentFilter:
    @classmethod
    def check_text(cls, text: str) -> dict:
        text_lower = (text or "").lower()
        found = [kw for kw in BLOCKED_KEYWORDS if kw in text_lower]
        return {"passed": len(found) == 0, "blocked_keywords": found}

    @classmethod
    def check_creative(cls, creative) -> dict:
        combined = " ".join(filter(None, [
            creative.headline, creative.body_text,
            creative.cta_text, creative.advertiser_name,
        ]))
        result    = cls.check_text(combined)
        result["creative_id"] = creative.id
        return result

    @classmethod
    def is_category_allowed(cls, category: str) -> bool:
        return category.lower() in ALLOWED_CATEGORIES
