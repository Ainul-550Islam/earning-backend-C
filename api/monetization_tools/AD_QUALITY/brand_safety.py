"""AD_QUALITY/brand_safety.py — Brand safety classification."""
UNSAFE_CONTENT_TYPES = [
    "adult", "gambling", "alcohol", "tobacco", "weapons",
    "hate_speech", "violence", "drugs", "misinformation",
]

BRAND_SAFE_DOMAINS = [
    "bbc.com", "cnn.com", "reuters.com", "google.com",
    "facebook.com", "youtube.com",
]


class BrandSafetyChecker:
    @classmethod
    def is_safe(cls, content_type: str = None,
                 domain: str = None) -> dict:
        issues = []
        if content_type and content_type.lower() in UNSAFE_CONTENT_TYPES:
            issues.append(f"Unsafe content type: {content_type}")
        return {"brand_safe": len(issues) == 0, "issues": issues, "domain": domain}

    @classmethod
    def score(cls, creative) -> float:
        score = 1.0
        text  = " ".join(filter(None, [creative.headline, creative.body_text]))
        from .ad_content_filter import BLOCKED_KEYWORDS
        for kw in BLOCKED_KEYWORDS:
            if kw in (text or "").lower():
                score -= 0.2
        return max(0.0, score)
