"""
AutoModAdapter
==============
Wraps api.auto_mod for engagement content moderation.

Used for:
    - Guild name/description validation before creation
    - Social feed post content check
    - Chat messages in guild
    - Achievement/quest names (admin input sanitisation)
    - User-generated challenge titles
"""

import logging
logger = logging.getLogger("engagement.adapters.auto_mod")

# Max content lengths
MAX_LENGTHS = {
    "guild_name":        50,
    "guild_description": 500,
    "feed_post":         280,
    "guild_message":     500,
    "challenge_title":   100,
}


class AutoModAdapter:

    @staticmethod
    def check_text(text: str, context: str = "general",
                   user=None) -> dict:
        """
        Check text content for violations.

        Returns:
            {
                "allowed": bool,
                "reason": str,       # "" if allowed
                "filtered_text": str # cleaned version (if auto-filter)
                "confidence": float,
                "source": str,
            }
        """
        if not text or not text.strip():
            return {"allowed": True, "reason": "", "filtered_text": text,
                    "confidence": 1.0, "source": "empty"}

        # Check length
        max_len = MAX_LENGTHS.get(context, 500)
        if len(text) > max_len:
            return {"allowed": False, "reason": "too_long",
                    "filtered_text": text[:max_len], "confidence": 1.0,
                    "source": "length_check"}

        try:
            from api.auto_mod.services import ContentModerationService
            result = ContentModerationService().check(
                text=text,
                context=context,
                user_id=getattr(user, "pk", None),
            )
            return {
                "allowed":       result.get("allowed", True),
                "reason":        result.get("reason", ""),
                "filtered_text": result.get("filtered_text", text),
                "confidence":    result.get("confidence", 1.0),
                "source":        "auto_mod_app",
            }
        except Exception as e:
            logger.debug(f"AutoModAdapter.check_text: {e}")
            # Minimal profanity check fallback
            BLOCKED_WORDS = {"spam", "scam", "hack", "cheat"}
            lower = text.lower()
            for w in BLOCKED_WORDS:
                if w in lower:
                    return {"allowed": False, "reason": "profanity",
                            "filtered_text": text, "confidence": 0.9,
                            "source": "local_filter"}
            return {"allowed": True, "reason": "", "filtered_text": text,
                    "confidence": 1.0, "source": "unavailable"}

    @staticmethod
    def check_guild_name(name: str, user=None) -> dict:
        return AutoModAdapter.check_text(name, "guild_name", user)

    @staticmethod
    def check_feed_post(text: str, user=None) -> dict:
        return AutoModAdapter.check_text(text, "feed_post", user)

    @staticmethod
    def check_guild_message(text: str, user=None) -> dict:
        return AutoModAdapter.check_text(text, "guild_message", user)