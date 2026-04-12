"""
api/ai_engine/PERSONALIZATION/preference_learning.py
=====================================================
Preference Learning — explicit + implicit feedback থেকে user preferences শেখো।
Click, complete, skip, rate signals সব use করো।
Online learning — প্রতিটি interaction এ model update হয়।
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PreferenceLearner:
    """
    Online preference learning engine।
    User এর interaction signals থেকে continuously learn করো।
    """

    # Signal weights — কোন action কতটা strong signal
    SIGNAL_WEIGHTS = {
        "complete":     1.00,   # Strongest positive
        "rate_5star":   0.90,
        "rate_4star":   0.70,
        "click":        0.40,
        "view_long":    0.25,   # >30 seconds view
        "view_short":   0.10,   # <5 seconds view
        "rate_3star":   0.00,   # Neutral
        "skip":        -0.30,   # Negative
        "rate_1star":  -0.60,
        "rate_2star":  -0.40,
        "hide":        -0.80,   # Strong negative
        "report":      -1.00,   # Strongest negative
    }

    def record_interaction(self, user, interaction: dict,
                            tenant_id=None) -> dict:
        """
        User interaction record করো ও preferences update করো।

        interaction: {
            "item_id": "...",
            "item_type": "offer",
            "action": "complete",
            "category": "survey",
            "reward": 200,
            "difficulty": "medium",
        }
        """
        action   = interaction.get("action", "view_short")
        weight   = self.SIGNAL_WEIGHTS.get(action, 0.1)
        category = interaction.get("category", "")
        reward   = float(interaction.get("reward", 0))
        diff     = interaction.get("difficulty", "medium")
        item_type = interaction.get("item_type", "offer")

        # Update personalization profile
        profile_updates = self._calculate_profile_updates(
            weight, category, reward, diff, item_type
        )
        self._apply_updates(user, profile_updates, tenant_id)

        return {
            "interaction_recorded": True,
            "action":               action,
            "signal_weight":        weight,
            "updates_applied":      list(profile_updates.keys()),
            "is_positive":          weight > 0,
        }

    def _calculate_profile_updates(self, weight: float, category: str,
                                     reward: float, difficulty: str,
                                     item_type: str) -> Dict:
        """Profile update values calculate করো।"""
        updates = {}

        # Category preference
        if category and abs(weight) > 0.2:
            updates["category"] = {"name": category, "weight": weight}

        # Difficulty preference
        if difficulty and weight > 0.3:
            updates["difficulty"] = {"level": difficulty, "weight": weight}

        # Reward sensitivity
        if reward > 0 and weight > 0:
            updates["reward_sensitivity"] = {
                "reward": reward,
                "liked": weight > 0.5,
            }

        # Item type preference
        if weight > 0.4:
            updates["item_type"] = {"type": item_type, "weight": weight}

        return updates

    def _apply_updates(self, user, updates: Dict, tenant_id=None):
        """Profile DB update করো।"""
        try:
            from ..models import PersonalizationProfile
            from django.utils import timezone

            profile, _ = PersonalizationProfile.objects.get_or_create(
                user=user,
                defaults={"tenant_id": tenant_id}
            )

            # Update preferred categories
            if "category" in updates:
                cat_update = updates["category"]
                cats       = list(profile.preferred_categories or [])
                cat_name   = cat_update["name"]
                if cat_update["weight"] > 0:
                    if cat_name not in cats:
                        cats.insert(0, cat_name)
                    else:
                        # Move to front (reinforce preference)
                        cats.remove(cat_name)
                        cats.insert(0, cat_name)
                    profile.preferred_categories = cats[:10]
                elif cat_name in cats:
                    cats.remove(cat_name)
                    profile.preferred_categories = cats

            profile.last_refreshed = timezone.now()
            profile.save(update_fields=["preferred_categories", "last_refreshed"])

        except Exception as e:
            logger.error(f"Preference update error for user {user.id}: {e}")

    def learn_from_batch(self, interactions: List[Dict],
                          user=None, tenant_id=None) -> dict:
        """Batch interactions থেকে learn করো।"""
        if not interactions:
            return {"learned": False}

        positive = sum(1 for i in interactions if self.SIGNAL_WEIGHTS.get(i.get("action", ""), 0) > 0)
        negative = sum(1 for i in interactions if self.SIGNAL_WEIGHTS.get(i.get("action", ""), 0) < 0)

        # Category frequency analysis
        cat_signals: Dict[str, float] = {}
        for interaction in interactions:
            cat    = interaction.get("category", "")
            action = interaction.get("action", "view_short")
            weight = self.SIGNAL_WEIGHTS.get(action, 0)
            if cat:
                cat_signals[cat] = cat_signals.get(cat, 0) + weight

        top_categories = sorted(
            [(cat, score) for cat, score in cat_signals.items() if score > 0],
            key=lambda x: x[1], reverse=True
        )[:5]

        if user and top_categories:
            try:
                from ..models import PersonalizationProfile
                profile, _ = PersonalizationProfile.objects.get_or_create(user=user)
                profile.preferred_categories = [cat for cat, _ in top_categories]
                profile.save(update_fields=["preferred_categories"])
            except Exception as e:
                logger.error(f"Batch preference update error: {e}")

        return {
            "learned":          True,
            "total_interactions": len(interactions),
            "positive_signals": positive,
            "negative_signals": negative,
            "top_categories":   top_categories,
            "learning_quality": "high" if len(interactions) >= 20 else "medium" if len(interactions) >= 5 else "low",
        }

    def get_preference_vector(self, user) -> Dict:
        """User এর preference vector generate করো।"""
        try:
            from ..models import PersonalizationProfile
            profile = PersonalizationProfile.objects.filter(user=user).first()
            if not profile:
                return {"status": "no_profile", "vector": {}}

            return {
                "preferred_categories":  profile.preferred_categories or [],
                "preferred_offer_types": profile.preferred_offer_types or [],
                "preferred_time_slots":  profile.preferred_time_slots or [],
                "is_deal_seeker":        profile.is_deal_seeker,
                "price_sensitivity":     float(profile.price_sensitivity or 0.5),
                "engagement_score":      float(profile.engagement_score or 0.5),
                "ltv_segment":           profile.ltv_segment or "medium",
                "vector_quality":        "rich" if profile.preferred_categories else "sparse",
            }
        except Exception as e:
            return {"error": str(e)}

    def cold_start_preferences(self, user, signup_data: dict = None) -> dict:
        """
        New user preferences initialize করো।
        Registration data + country + device signals use করো।
        """
        signup_data = signup_data or {}
        country     = signup_data.get("country", getattr(user, "country", "BD"))
        age_group   = signup_data.get("age_group", "18-25")
        interests   = signup_data.get("interests", [])

        # Country-based defaults
        country_defaults = {
            "BD": {"preferred_categories": ["survey", "app_install", "video"], "language": "bn"},
            "IN": {"preferred_categories": ["survey", "gaming", "app_install"],  "language": "hi"},
            "US": {"preferred_categories": ["survey", "product_review", "video"], "language": "en"},
        }
        defaults = country_defaults.get(country, {"preferred_categories": ["survey"], "language": "en"})

        if interests:
            defaults["preferred_categories"] = interests + defaults["preferred_categories"]

        try:
            from ..models import PersonalizationProfile
            profile, created = PersonalizationProfile.objects.get_or_create(user=user)
            if created or not profile.preferred_categories:
                profile.preferred_categories = defaults["preferred_categories"][:5]
                profile.save(update_fields=["preferred_categories"])
        except Exception as e:
            logger.error(f"Cold start error: {e}")

        return {
            "initialized":     True,
            "country":         country,
            "defaults_applied": defaults,
        }
