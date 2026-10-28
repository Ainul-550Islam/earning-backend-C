"""
api/gamification/integrations/users_adapter.py

Users ↔ Gamification adapter।

User lifecycle events (login, KYC, tier upgrade) থেকে
gamification milestone/badge trigger করে।

Wire-up (api/users/apps.py ready() তে):
    from api.gamification.integrations.users_adapter import UsersGamificationAdapter
    UsersGamificationAdapter().connect_signals()
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# api.users.constants.UserEvent থেকে নেওয়া values
FIRST_LOGIN      = "first_login"
PROFILE_UPDATED  = "profile_updated"
KYC_APPROVED     = "kyc_approved"
WITHDRAWAL_REQ   = "withdrawal_requested"
REFERRAL_JOINED  = "referral_joined"

# Event → achievement title + points map
EVENT_ACHIEVEMENT_MAP = {
    FIRST_LOGIN: {
        "title":       "Welcome Aboard!",
        "description": "প্রথম লগইন সম্পন্ন করেছেন।",
        "points":      5,
        "badge":       "first_login",
        "once":        True,   # only once
    },
    PROFILE_UPDATED: {
        "title":       "Profile Complete",
        "description": "প্রোফাইল সম্পূর্ণ করেছেন।",
        "points":      10,
        "badge":       "profile_complete",
        "once":        True,
    },
    KYC_APPROVED: {
        "title":       "KYC Verified",
        "description": "পরিচয় যাচাই সম্পন্ন হয়েছে।",
        "points":      50,
        "badge":       "kyc_verified",
        "once":        True,
    },
    WITHDRAWAL_REQ: {
        "title":       "First Withdrawal",
        "description": "প্রথম উত্তোলন অনুরোধ করেছেন।",
        "points":      20,
        "badge":       "first_withdrawal",
        "once":        True,
    },
    REFERRAL_JOINED: {
        "title":       "Referral Champion",
        "description": "প্রথম referral সফলভাবে সম্পন্ন।",
        "points":      30,
        "badge":       "referral_first",
        "once":        True,
    },
}

# Tier → achievement title + points
TIER_ACHIEVEMENT_MAP = {
    "BRONZE":   {"title": "Bronze Member",   "points": 10},
    "SILVER":   {"title": "Silver Member",   "points": 25},
    "GOLD":     {"title": "Gold Member",     "points": 50},
    "PLATINUM": {"title": "Platinum Member", "points": 100},
    "DIAMOND":  {"title": "Diamond Member",  "points": 250},
}


class UsersGamificationAdapter:
    """User lifecycle events থেকে gamification achievements trigger করে।"""

    def on_event(self, user: Any, event: str, context: dict = None) -> None:
        """
        User event হলে — matching achievement award করো।

        Args:
            user:    Django User instance
            event:   Event name (UserEvent constant)
            context: Extra context (e.g. referral data)
        """
        config = EVENT_ACHIEVEMENT_MAP.get(event)
        if not config:
            logger.debug("[UsersGamificationAdapter] Unknown event: %s", event)
            return

        try:
            self._award(
                user=user,
                title=config["title"],
                description=config["description"],
                points=config["points"],
                metadata={
                    "badge": config.get("badge", event),
                    "event": event,
                    **(context or {}),
                },
            )
            self._track(user, f"user_event_{event}", context or {})
        except Exception as exc:
            logger.error("[UsersGamificationAdapter] on_event(%s) failed: %s", event, exc)

    def on_tier_changed(self, user: Any, old_tier: str, new_tier: str) -> None:
        """
        Tier upgrade হলে — tier achievement award করো।

        Args:
            user:     Django User instance
            old_tier: Previous tier (e.g. "BRONZE")
            new_tier: New tier (e.g. "GOLD")
        """
        config = TIER_ACHIEVEMENT_MAP.get(new_tier.upper())
        if not config:
            return

        try:
            self._award(
                user=user,
                title=config["title"],
                description=f"{old_tier} থেকে {new_tier}-এ উন্নীত হয়েছেন!",
                points=config["points"],
                metadata={
                    "old_tier": old_tier,
                    "new_tier": new_tier,
                    "badge": f"tier_{new_tier.lower()}",
                },
            )
            self._track(user, "tier_upgraded", {"old_tier": old_tier, "new_tier": new_tier})
        except Exception as exc:
            logger.error("[UsersGamificationAdapter] on_tier_changed failed: %s", exc)

    def connect_signals(self) -> None:
        """
        api.users সিগনালগুলো gamification-এর সাথে connect করো।
        api/users/apps.py-এর ready()-তে call করো।

        Example:
            class UsersConfig(AppConfig):
                def ready(self):
                    from api.gamification.integrations.users_adapter import (
                        UsersGamificationAdapter
                    )
                    UsersGamificationAdapter().connect_signals()
        """
        try:
            from django.contrib.auth import user_logged_in
            from django.dispatch import receiver

            adapter = self

            @receiver(user_logged_in)
            def _on_login(sender, request, user, **kwargs):
                adapter.on_event(user=user, event=FIRST_LOGIN)

        except Exception as exc:
            logger.error("[UsersGamificationAdapter] connect_signals failed: %s", exc)

        # KYC signal
        try:
            from django.db.models.signals import post_save

            adapter = self

            @post_save.connect
            def _on_kyc_approved(sender, instance, **kwargs):
                # api.kyc.models.KYCSubmission
                if sender.__name__ == "KYCSubmission" and getattr(instance, "status", "") == "approved":
                    user = getattr(instance, "user", None)
                    if user:
                        adapter.on_event(user=user, event=KYC_APPROVED)

        except Exception as exc:
            logger.debug("[UsersGamificationAdapter] KYC signal connect failed: %s", exc)

        logger.info("[UsersGamificationAdapter] Signals connected.")

    # ── Private ────────────────────────────────────────────────────────────────

    def _award(self, user: Any, title: str, description: str, points: int,
               metadata: dict) -> None:
        """gamification service-এর award_achievement call করো।"""
        from api.gamification.services import award_achievement
        from api.gamification.choices import AchievementType

        award_achievement(
            user_id=user.pk,
            achievement_type=AchievementType.BADGE,
            title=title,
            description=description,
            points=points,
            metadata=metadata,
        )

    def _track(self, user: Any, event: str, properties: dict) -> None:
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
