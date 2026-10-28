"""
api/gamification/integrations/payout_queue_adapter.py

PayoutQueue ↔ Gamification adapter।

payout_item_succeeded → first payout milestone।
payout_batch_completed → batch bonus।

Wire-up (api/payout_queue/receivers.py-তে add করো):
    from api.gamification.integrations.payout_queue_adapter import PayoutQueueGamificationAdapter
    _pq = PayoutQueueGamificationAdapter()
    # on_payout_item_succeeded receiver-এর শেষে:
    _pq.on_payout_succeeded(item=item)
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

PAYOUT_COUNT_MILESTONES = {
    1:   {"title": "First Payout!",      "points": 30},
    5:   {"title": "Regular Earner",     "points": 50},
    10:  {"title": "Consistent Earner",  "points": 100},
    25:  {"title": "Payout Pro",         "points": 200},
    50:  {"title": "Payout Master",      "points": 500},
}


class PayoutQueueGamificationAdapter:

    def on_payout_succeeded(self, item: Any) -> None:
        """payout_item_succeeded হলে milestone check করো।"""
        user = self._get_user(item)
        if not user:
            return
        try:
            count = self._get_payout_count(user)
            cfg   = PAYOUT_COUNT_MILESTONES.get(count)
            if cfg:
                self._award(user, cfg["title"],
                            f"মোট {count}টি সফল payout সম্পন্ন!",
                            cfg["points"],
                            {"source": "payout_queue", "payout_count": count,
                             "item_id": str(getattr(item, "id", ""))})
            self._track(user, "payout_item_succeeded", {
                "amount":    float(getattr(item, "net_amount", 0) or 0),
                "item_id":   str(getattr(item, "id", "")),
            })
        except Exception as exc:
            logger.error("[PayoutQueueAdapter] on_payout_succeeded failed: %s", exc)

    def on_payout_failed(self, item: Any) -> None:
        """payout_item_permanently_failed — শুধু track করো।"""
        user = self._get_user(item)
        if not user:
            return
        try:
            self._track(user, "payout_item_failed", {
                "item_id":    str(getattr(item, "id", "")),
                "error_code": str(getattr(item, "error_code", "")),
            })
        except Exception as exc:
            logger.error("[PayoutQueueAdapter] on_payout_failed failed: %s", exc)

    def _get_user(self, item: Any) -> Any:
        user = getattr(item, "user", None)
        if user:
            return user
        user_id = getattr(item, "user_id", None)
        if user_id:
            try:
                from django.contrib.auth import get_user_model
                return get_user_model().objects.get(pk=user_id)
            except Exception:
                pass
        return None

    def _get_payout_count(self, user: Any) -> int:
        try:
            from django.apps import apps
            for m in ("PayoutItem", "PayoutRecord"):
                try:
                    M = apps.get_model("payout_queue", m)
                    return M.objects.filter(user=user, status="succeeded").count()
                except (LookupError, Exception):
                    continue
        except Exception:
            pass
        return 0

    def _award(self, user, title, description, points, metadata):
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType
        try:
            award_achievement(user_id=user.pk, achievement_type=AchievementType.MILESTONE,
                              title=title, description=description, points=points, metadata=metadata)
        except Exception as exc:
            logger.debug("[PayoutQueueAdapter] _award skipped: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
