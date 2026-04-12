"""
api/ai_engine/PERSONALIZATION/dynamic_personalization.py
=========================================================
Dynamic Personalization — real-time context-aware adaptation।
প্রতিটি request এর context অনুযায়ী experience dynamically পরিবর্তন করো।
Time, device, location, behavior সব real-time signals।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DynamicPersonalizer:
    """
    Real-time dynamic personalization engine।
    Every request এ context signals process করো।
    """

    # Time-of-day strategy mapping
    TIME_STRATEGIES = {
        "early_morning":  (5,  8,  "quick_tasks",        "সকালের জন্য দ্রুত কাজ"),
        "morning":        (8,  12, "high_value",          "সকালের premium অফার"),
        "lunch":          (12, 14, "medium_tasks",        "লাঞ্চ ব্রেকের জন্য"),
        "afternoon":      (14, 17, "variety",             "বিকেলের mixed অফার"),
        "evening":        (17, 21, "high_reward",         "সন্ধ্যার high-reward অফার"),
        "late_evening":   (21, 24, "passive_easy",        "রাতের সহজ অফার"),
        "night":          (0,  5,  "passive_earning",     "রাতের passive income"),
    }

    def personalize(self, user, context: dict) -> dict:
        """Real-time personalization decision।"""
        hour    = context.get("hour", 12)
        device  = context.get("device", "mobile")
        country = context.get("country", getattr(user, "country", "BD"))
        lang    = context.get("language", getattr(user, "language", "bn"))
        session_depth = context.get("session_depth", 1)  # How many pages visited

        strategy    = self._get_time_strategy(hour)
        ui_adapt    = self._ui_adaptation(device, lang)
        content     = self._content_strategy(user, strategy, session_depth)
        notif_timing = self._notification_timing(hour, device)

        return {
            "strategy":          strategy["name"],
            "strategy_message":  strategy["message"],
            "ui_adaptation":     ui_adapt,
            "content_strategy":  content,
            "notification":      notif_timing,
            "country":           country,
            "context_hash":      self._context_hash(hour, device, country),
        }

    def _get_time_strategy(self, hour: int) -> dict:
        """Hour of day → content strategy।"""
        for name, (start, end, strategy, message) in self.TIME_STRATEGIES.items():
            if start <= hour < end:
                return {
                    "name":       strategy,
                    "period":     name,
                    "message":    message,
                    "hour":       hour,
                }
        return {"name": "balanced", "period": "default", "message": "সেরা অফার", "hour": hour}

    def _ui_adaptation(self, device: str, language: str) -> dict:
        """Device ও language based UI adaptation।"""
        mobile_ui = {
            "card_size":         "compact",
            "items_per_row":     1,
            "show_images":       True,
            "text_length":       "short",
            "cta_size":          "large",
            "infinite_scroll":   True,
        }
        desktop_ui = {
            "card_size":         "full",
            "items_per_row":     3,
            "show_images":       True,
            "text_length":       "full",
            "cta_size":          "medium",
            "infinite_scroll":   False,
        }

        ui = mobile_ui if device == "mobile" else desktop_ui

        # Language-specific adjustments
        rtl_languages = {"ar", "ur", "fa"}
        ui["direction"] = "rtl" if language in rtl_languages else "ltr"
        ui["font"]      = "bengali" if language == "bn" else "default"

        return {**ui, "device": device, "language": language}

    def _content_strategy(self, user, strategy: dict, session_depth: int) -> dict:
        """Session depth ও strategy based content decisions।"""
        strat_name = strategy.get("name", "balanced")

        content = {
            "primary_offer_type":   "easy" if strat_name in ("quick_tasks", "passive_easy") else "high_value",
            "show_streak_reminder": session_depth == 1,  # First page only
            "show_referral_cta":    session_depth >= 3 and getattr(user, "referral_count_today", 0) < 2,
            "show_withdrawal_cta":  float(getattr(user, "coin_balance", 0)) >= 500,
            "show_daily_bonus":     session_depth == 1,
            "max_offers_shown":     5 if strat_name == "quick_tasks" else 10,
            "sort_by":              "reward" if strat_name == "high_reward" else "conversion_rate",
        }
        return content

    def _notification_timing(self, current_hour: int, device: str) -> dict:
        """Optimal notification timing suggest করো।"""
        peak_hours = [8, 9, 10, 13, 18, 19, 20, 21]
        next_peak  = next((h for h in peak_hours if h > current_hour), peak_hours[0])

        return {
            "should_show_now":      current_hour in peak_hours,
            "next_optimal_hour":    next_peak,
            "push_enabled":         device == "mobile",
            "notification_priority": "high" if current_hour in [8, 9, 19, 20] else "normal",
        }

    def _context_hash(self, hour: int, device: str, country: str) -> str:
        """Context fingerprint — caching এর জন্য।"""
        hour_bucket = hour // 3  # 8 buckets per day
        return f"{hour_bucket}_{device[:3]}_{country[:2]}"

    def get_personalization_report(self, user) -> dict:
        """User এর complete personalization status report।"""
        from ..utils import days_since
        from ..models import PersonalizationProfile, RecommendationResult

        profile = PersonalizationProfile.objects.filter(user=user).first()
        total_recs = RecommendationResult.objects.filter(user=user).count()
        clicked    = RecommendationResult.objects.filter(
            user=user
        ).exclude(clicked_item_id="").count()

        return {
            "user_id":               str(user.id),
            "profile_exists":        profile is not None,
            "preferred_categories":  (profile.preferred_categories or []) if profile else [],
            "ltv_segment":           (profile.ltv_segment or "unknown") if profile else "unknown",
            "engagement_score":      float((profile.engagement_score or 0)) if profile else 0,
            "total_recommendations": total_recs,
            "total_clicks":          clicked,
            "ctr":                   round(clicked / max(total_recs, 1), 4),
            "days_since_last_activity": days_since(user.last_login),
            "personalization_quality": "rich" if profile and profile.preferred_categories else "cold_start",
        }
