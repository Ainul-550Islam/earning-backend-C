"""
api/gamification/integrations/security_adapter.py

Security ↔ Gamification protection adapter।

UserBan → achievements freeze/unfreeze।
SecurityIncident → high-risk users-এর achievements pause।

Wire-up (api/security/serializers.py এ existing post_save.connect এর পরে):
    from api.gamification.integrations.security_adapter import SecurityGamificationAdapter
    post_save.connect(SecurityGamificationAdapter().on_user_ban_save, sender=UserBan)
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)


class SecurityGamificationAdapter:

    def on_user_ban_save(self, sender, instance, created, **kwargs) -> None:
        """
        UserBan created/updated → gamification achievements freeze করো।
        UserBan expired/lifted → achievements unfreeze করো।
        """
        try:
            user   = getattr(instance, "user", None)
            status = str(getattr(instance, "status", "") or "")
            reason = str(getattr(instance, "reason", "") or "")

            if not user:
                return

            if status in ("active", "permanent") and created:
                self._freeze_achievements(user, reason=reason,
                                          ban_id=str(getattr(instance, "id", "")))
            elif status in ("expired", "lifted", "removed"):
                self._unfreeze_achievements(user)
        except Exception as exc:
            logger.error("[SecurityAdapter] on_user_ban_save failed: %s", exc)

    def on_security_incident(self, incident: Any) -> None:
        """
        High-severity SecurityIncident → user achievements pause করো।
        """
        try:
            user     = getattr(incident, "user", None)
            severity = str(getattr(incident, "severity", "") or "").lower()
            if not user or severity not in ("high", "critical"):
                return
            self._freeze_achievements(user, reason=f"security_incident:{severity}",
                                      incident_id=str(getattr(incident, "id", "")))
            self._track(user, "security_achievement_frozen", {
                "severity": severity,
                "incident_id": str(getattr(incident, "id", "")),
            })
        except Exception as exc:
            logger.error("[SecurityAdapter] on_security_incident failed: %s", exc)

    def check_user_is_banned(self, user: Any) -> bool:
        """
        award_achievement-এর আগে call করো — banned user-দের achievements দেওয়া যাবে না।
        Returns True if user has an active ban।
        """
        try:
            from django.apps import apps
            M = apps.get_model("security", "UserBan")
            return M.objects.filter(user=user, status="active").exists()
        except (LookupError, ImportError):
            return False
        except Exception as exc:
            logger.debug("[SecurityAdapter] check_user_is_banned failed: %s", exc)
            return False

    def _freeze_achievements(self, user: Any, reason: str = "", **meta) -> None:
        """
        User-এর pending/unawarded achievements mark করো — future awards block করো।
        Implementation: UserAchievement-এর metadata-তে 'frozen' flag set করো।
        """
        try:
            from api.gamification.models import UserAchievement
            UserAchievement.objects.filter(
                user=user, is_awarded=False
            ).update(metadata={"frozen": True, "freeze_reason": reason, **meta})
            logger.warning("[SecurityAdapter] Achievements frozen for user=%s reason=%s",
                           getattr(user, "id", "?"), reason[:100])
        except Exception as exc:
            logger.error("[SecurityAdapter] _freeze_achievements failed: %s", exc)

    def _unfreeze_achievements(self, user: Any) -> None:
        """Ban lifted → achievements unfreeze করো।"""
        try:
            from api.gamification.models import UserAchievement
            frozen = UserAchievement.objects.filter(user=user, is_awarded=False,
                                                    metadata__frozen=True)
            for ach in frozen:
                meta = ach.metadata or {}
                meta.pop("frozen", None)
                meta.pop("freeze_reason", None)
                ach.metadata = meta
                ach.save(update_fields=["metadata"])
            logger.info("[SecurityAdapter] Achievements unfrozen for user=%s (%d records)",
                        getattr(user, "id", "?"), frozen.count())
        except Exception as exc:
            logger.error("[SecurityAdapter] _unfreeze_achievements failed: %s", exc)

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
