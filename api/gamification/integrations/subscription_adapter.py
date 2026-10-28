"""
api/gamification/integrations/subscription_adapter.py

Subscription ↔ Gamification adapter।

subscription_activated / renewed / plan_changed → milestone achievement।

Wire-up (api/subscription/receivers.py-তে signal connect করো):
    from api.gamification.integrations.subscription_adapter import SubscriptionGamificationAdapter
    _sub_adapter = SubscriptionGamificationAdapter()
    subscription_activated.connect(_sub_adapter.on_activated)
    subscription_renewed.connect(_sub_adapter.on_renewed)
    plan_changed.connect(_sub_adapter.on_plan_changed)
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

PLAN_ACHIEVEMENTS = {
    "basic":    {"title": "Subscriber",       "points": 20},
    "standard": {"title": "Pro Subscriber",   "points": 50},
    "premium":  {"title": "Elite Subscriber", "points": 100},
    "enterprise":{"title":"Enterprise Member","points": 200},
}

RENEWAL_MILESTONE_POINTS = 15  # প্রতি renewal-এ


class SubscriptionGamificationAdapter:

    def on_activated(self, sender, instance, **kwargs) -> None:
        """subscription_activated signal → Subscriber badge।"""
        user = getattr(instance, "user", None)
        if not user:
            return
        try:
            plan_name = str(getattr(getattr(instance, "plan", None), "name", "basic") or "basic").lower()
            cfg = PLAN_ACHIEVEMENTS.get(plan_name, {"title": "Subscriber", "points": 20})
            self._award(user, cfg["title"],
                        f"{plan_name.title()} plan activate করেছেন!",
                        cfg["points"],
                        {"source": "subscription", "plan": plan_name, "event": "activated"})
            self._track(user, "subscription_activated", {"plan": plan_name})
        except Exception as exc:
            logger.error("[SubscriptionAdapter] on_activated failed: %s", exc)

    def on_renewed(self, sender, instance, **kwargs) -> None:
        """subscription_renewed signal → renewal bonus।"""
        user = getattr(instance, "user", None)
        if not user:
            return
        try:
            self._award(user, "Loyal Subscriber",
                        "Subscription renewal করেছেন!",
                        RENEWAL_MILESTONE_POINTS,
                        {"source": "subscription", "event": "renewed",
                         "sub_id": str(getattr(instance, "id", ""))})
            self._track(user, "subscription_renewed", {})
        except Exception as exc:
            logger.error("[SubscriptionAdapter] on_renewed failed: %s", exc)

    def on_plan_changed(self, sender, instance, old_plan=None, new_plan=None, **kwargs) -> None:
        """plan_changed signal — upgrade হলে bonus দাও।"""
        user = getattr(instance, "user", None)
        if not user or not new_plan:
            return
        try:
            new_name  = str(getattr(new_plan, "name", "") or "").lower()
            old_name  = str(getattr(old_plan, "name", "") or "").lower()
            new_cfg   = PLAN_ACHIEVEMENTS.get(new_name)
            old_cfg   = PLAN_ACHIEVEMENTS.get(old_name, {"points": 0})
            if new_cfg and new_cfg["points"] > old_cfg["points"]:
                self._award(user, f"Upgraded to {new_name.title()}",
                            f"{old_name.title()} থেকে {new_name.title()}-এ upgrade করেছেন!",
                            new_cfg["points"] - old_cfg["points"],
                            {"source": "subscription", "event": "plan_upgraded",
                             "old_plan": old_name, "new_plan": new_name})
            self._track(user, "subscription_plan_changed",
                        {"old_plan": old_name, "new_plan": new_name})
        except Exception as exc:
            logger.error("[SubscriptionAdapter] on_plan_changed failed: %s", exc)

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.MILESTONE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[SubscriptionAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
