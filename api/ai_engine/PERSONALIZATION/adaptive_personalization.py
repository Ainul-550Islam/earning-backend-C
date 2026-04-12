"""
api/ai_engine/PERSONALIZATION/adaptive_personalization.py
=========================================================
Adaptive Personalization — নিজে নিজে শেখে ও adapt করে।
User feedback loop → continuous improvement।
A/B test results, engagement signals, preference drift detection।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AdaptivePersonalizer:
    """
    Self-improving personalization engine।
    Feedback → Update → Improve cycle।
    """

    ADAPTATION_SIGNALS = {
        "click":         +0.10,
        "complete":      +0.30,
        "share":         +0.25,
        "rate_high":     +0.20,
        "skip":          -0.15,
        "hide":          -0.25,
        "rate_low":      -0.20,
        "report":        -0.40,
        "long_view":     +0.15,
        "quick_exit":    -0.10,
    }

    def adapt(self, user, feedback_events: List[Dict],
               learning_rate: float = 0.1) -> dict:
        """Feedback events থেকে user profile adapt করো।"""
        if not feedback_events:
            return {"adapted": False, "reason": "No feedback events"}

        # Aggregate signals
        category_signals: Dict[str, float]  = {}
        difficulty_signals: Dict[str, float] = {}
        time_signals: Dict[int, float]       = {}

        for event in feedback_events:
            action     = event.get("action", "view")
            weight     = self.ADAPTATION_SIGNALS.get(action, 0.0)
            category   = event.get("category", "")
            difficulty = event.get("difficulty", "")
            hour       = event.get("hour", 12)

            if category and weight != 0:
                category_signals[category] = category_signals.get(category, 0.0) + weight

            if difficulty and weight != 0:
                difficulty_signals[difficulty] = difficulty_signals.get(difficulty, 0.0) + weight

            if weight != 0:
                time_signals[hour] = time_signals.get(hour, 0.0) + weight

        # Apply to profile
        updates = self._apply_signals(user, category_signals, difficulty_signals,
                                       time_signals, learning_rate)

        return {
            "adapted":           True,
            "events_processed":  len(feedback_events),
            "updates":           updates,
            "learning_quality":  "rich" if len(feedback_events) >= 20 else "sparse",
        }

    def _apply_signals(self, user, cat_signals: Dict, diff_signals: Dict,
                        time_signals: Dict, lr: float) -> Dict:
        """Signals → profile updates।"""
        updates = {}
        try:
            from ..models import PersonalizationProfile
            from django.utils import timezone

            profile, _ = PersonalizationProfile.objects.get_or_create(user=user)

            # Update preferred categories
            if cat_signals:
                current_cats = list(profile.preferred_categories or [])
                # Positive signal → add to front; negative → remove
                positive_cats = sorted(
                    [(cat, score) for cat, score in cat_signals.items() if score > 0],
                    key=lambda x: x[1], reverse=True
                )
                negative_cats = {cat for cat, score in cat_signals.items() if score < -0.2}

                new_cats = [cat for cat in current_cats if cat not in negative_cats]
                for cat, _ in positive_cats:
                    if cat not in new_cats:
                        new_cats.insert(0, cat)

                profile.preferred_categories = new_cats[:10]
                updates["preferred_categories"] = new_cats[:5]

            # Update preferred time slots
            if time_signals:
                top_hours = sorted(
                    time_signals.items(), key=lambda x: x[1], reverse=True
                )[:3]
                profile.preferred_time_slots = [f"{h:02d}:00" for h, _ in top_hours]
                updates["preferred_time_slots"] = profile.preferred_time_slots

            # Engagement score update
            total_signal   = sum(self.ADAPTATION_SIGNALS.get(e.get("action",""), 0)
                                   for e in [])  # Will recalculate
            current_score  = float(profile.engagement_score or 0.5)
            signal_sum     = sum(cat_signals.values()) if cat_signals else 0
            new_score      = max(0.0, min(1.0, current_score + lr * signal_sum * 0.1))
            profile.engagement_score = new_score
            updates["engagement_score"] = round(new_score, 4)

            profile.save(update_fields=["preferred_categories", "preferred_time_slots",
                                          "engagement_score"])

        except Exception as e:
            logger.error(f"Profile adaptation error: {e}")

        return updates

    def detect_preference_drift(self, user, lookback_days: int = 14) -> dict:
        """User preferences drift করেছে কিনা detect করো।"""
        try:
            from ..models import RecommendationResult, PersonalizationProfile
            from django.utils import timezone
            from datetime import timedelta

            since  = timezone.now() - timedelta(days=lookback_days)
            recent = RecommendationResult.objects.filter(
                user=user, created_at__gte=since
            ).values("recommended_items")[:100]

            recent_cats: Dict[str, int] = {}
            for rec in recent:
                for item in (rec["recommended_items"] or []):
                    cat = item.get("category", "")
                    if cat:
                        recent_cats[cat] = recent_cats.get(cat, 0) + 1

            profile     = PersonalizationProfile.objects.filter(user=user).first()
            stored_cats = set(profile.preferred_categories or []) if profile else set()
            recent_top  = set(list(sorted(recent_cats, key=recent_cats.get, reverse=True))[:5])

            overlap    = len(stored_cats & recent_top)
            total      = len(stored_cats | recent_top) or 1
            similarity = overlap / total
            has_drift  = similarity < 0.40

            return {
                "has_drift":         has_drift,
                "preference_similarity": round(similarity, 4),
                "stored_preferences":   list(stored_cats),
                "recent_preferences":   list(recent_top),
                "new_categories":       list(recent_top - stored_cats),
                "dropped_categories":   list(stored_cats - recent_top),
                "recommendation":       "Update user profile" if has_drift else "Preferences stable",
            }
        except Exception as e:
            return {"has_drift": False, "error": str(e)}

    def personalization_score(self, user) -> dict:
        """User এর personalization quality score।"""
        try:
            from ..models import PersonalizationProfile

            profile = PersonalizationProfile.objects.filter(user=user).first()
            if not profile:
                return {"score": 0.0, "quality": "no_profile"}

            score = 0.0
            if profile.preferred_categories:         score += 0.25
            if len(profile.preferred_categories or []) >= 3: score += 0.15
            if profile.preferred_offer_types:        score += 0.15
            if profile.preferred_time_slots:         score += 0.10
            if float(profile.engagement_score or 0) > 0.3: score += 0.20
            if profile.ltv_segment in ("high", "premium"): score += 0.15

            quality = "excellent" if score >= 0.80 else "good" if score >= 0.60 else "basic" if score >= 0.30 else "cold_start"

            return {
                "score":          round(score, 4),
                "quality":        quality,
                "data_richness":  "rich" if score >= 0.6 else "sparse",
                "recommendation": "Ready for deep personalization" if quality == "excellent"
                                  else "Collect more interaction data",
            }
        except Exception as e:
            return {"score": 0.0, "error": str(e)}
