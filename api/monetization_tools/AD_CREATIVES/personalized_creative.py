"""AD_CREATIVES/personalized_creative.py — User-personalized creative rendering."""
from typing import Optional


class PersonalizedCreativeEngine:
    """Renders creatives with user-specific content."""

    VARIABLE_TAGS = {
        "{{user_name}}": lambda u: getattr(u, "username", "Friend"),
        "{{user_country}}": lambda u: getattr(u, "country", ""),
        "{{coin_balance}}": lambda u: f"{getattr(u, 'coin_balance', 0):,.0f}",
        "{{streak_days}}": lambda u: str(getattr(u, "streak_days", 0)),
    }

    @classmethod
    def render(cls, template: str, user=None,
                extra_vars: dict = None) -> str:
        result = template
        for tag, fn in cls.VARIABLE_TAGS.items():
            if tag in result and user:
                try:
                    result = result.replace(tag, fn(user))
                except Exception:
                    pass
        for k, v in (extra_vars or {}).items():
            result = result.replace(f"{{{{{k}}}}}", str(v))
        return result

    @classmethod
    def supports_personalization(cls, creative_type: str) -> bool:
        return creative_type in ("html5", "native", "sponsored_content")
