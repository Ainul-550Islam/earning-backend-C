# engagement/services/anti_cheat_service.py
"""
Anti-Cheat Service
Checks every engagement action for suspicious patterns.
Fires asynchronously where possible to not block the API response.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum
from ..models.anti_cheat import AntiCheatRule, AntiCheatLog, UserRiskScore, IPReputation

logger = logging.getLogger(__name__)


class AntiCheatService:

    # ── Public check methods (called after each action) ───────────────────────

    @classmethod
    def check_spin_velocity(cls, user, ip_address: str = "", device_id: str = ""):
        """Flag if spins are happening too fast (bot behaviour)."""
        from ..models.spinwheel import SpinWheel
        from datetime import datetime
        now = timezone.now()
        # More than 5 spins in 60 seconds = suspicious
        recent = SpinWheel.objects.filter(user=user, spun_at__gte=now - timedelta(seconds=60)).count()
        if recent > 5:
            cls._flag(user, "spin-velocity", severity=2,
                      details={"spins_in_60s": recent},
                      ip_address=ip_address, device_id=device_id)

    @classmethod
    def check_checkin_ip(cls, user, ip_address: str = ""):
        """Flag if multiple different users check in from the same IP."""
        if not ip_address:
            return
        from ..models.checkin import DailyCheckIn
        today = timezone.now().date()
        # Check IP reputation first
        ip_rep = IPReputation.objects.filter(ip_address=ip_address, reputation="blocked").first()
        if ip_rep:
            cls._flag(user, "blocked-ip", severity=3,
                      details={"ip": ip_address, "reason": ip_rep.reason},
                      ip_address=ip_address)
            return
        # Count unique users from same IP today
        same_ip_count = AntiCheatLog.objects.filter(
            details__ip=ip_address, created_at__date=today
        ).values("user").distinct().count()
        if same_ip_count > 5:
            cls._flag(user, "ip-duplicate", severity=2,
                      details={"ip": ip_address, "users_from_ip": same_ip_count},
                      ip_address=ip_address)

    @classmethod
    def check_referral_abuse(cls, user):
        """Flag mass self-referral or coordinated referral farming."""
        from ..models.referral import Referral
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # More than 20 referrals in 24 hours is suspicious
        since = timezone.now() - timedelta(hours=24)
        count = Referral.objects.filter(referrer=user, created_at__gte=since).count()
        if count > 20:
            cls._flag(user, "referral-abuse", severity=3,
                      details={"referrals_in_24h": count})

    @classmethod
    def check_coin_velocity(cls, user):
        """Flag if a user earns an abnormal amount of coins in a short window."""
        from ..models.xp import XPTransaction
        since = timezone.now() - timedelta(hours=1)
        earned = XPTransaction.objects.filter(user=user, created_at__gte=since).aggregate(
            total=Sum("amount")
        )["total"] or 0
        if earned > 10000:
            cls._flag(user, "coin-velocity", severity=3,
                      details={"xp_in_1h": earned})

    # ── Risk score update ─────────────────────────────────────────────────────

    @classmethod
    def recalculate_risk(cls, user, tenant=None):
        """Recalculate user's risk score from open flags. Called by Celery."""
        risk, _ = UserRiskScore.objects.get_or_create(
            user=user, defaults={"tenant": tenant or getattr(user, "tenant", None)}
        )
        open_flags = AntiCheatLog.objects.filter(user=user, status="pending")
        flag_count = open_flags.count()
        max_severity = 0
        for flag in open_flags:
            max_severity = max(max_severity, flag.severity)

        score = min(100, flag_count * 15 + max_severity * 10)
        risk.score      = score
        risk.flag_count = flag_count
        if flag_count > 0:
            risk.last_flag_at = open_flags.order_by("-created_at").first().created_at
        risk.save(update_fields=["score", "flag_count", "last_flag_at"])

        if score >= 70 and not risk.is_suspended:
            risk.is_suspended       = True
            risk.suspended_at       = timezone.now()
            risk.suspension_reason  = f"Auto-suspended: risk score {score}"
            risk.save(update_fields=["is_suspended", "suspended_at", "suspension_reason"])
            logger.warning("AntiCheat: AUTO-SUSPENDED user=%s score=%d", user.pk, score)

    # ── Private helpers ───────────────────────────────────────────────────────

    @classmethod
    def _flag(cls, user, rule_slug: str, severity: int, details: dict,
              ip_address: str = "", device_id: str = ""):
        try:
            rule = AntiCheatRule.objects.get(slug=rule_slug, is_active=True)
        except AntiCheatRule.DoesNotExist:
            logger.debug("AntiCheat: rule '%s' not found or inactive", rule_slug)
            return

        AntiCheatLog.objects.create(
            user=user,
            tenant=getattr(user, "tenant", None),
            rule=rule,
            severity=severity,
            details=details,
            ip_address=ip_address or None,
            device_id=device_id,
        )
        logger.warning("AntiCheat FLAG: user=%s rule=%s severity=%d details=%s",
                       user.pk, rule_slug, severity, details)

    @classmethod
    def seed_default_rules(cls, tenant=None):
        """Create default anti-cheat rules if they don't exist."""
        defaults = [
            {"slug": "spin-velocity",   "name": "Spin Velocity",    "rule_type": "rate_limit",     "severity": 2, "threshold": 5,   "window_seconds": 60,   "action": "flag"},
            {"slug": "ip-duplicate",    "name": "IP Duplicate",     "rule_type": "ip_duplicate",   "severity": 2, "threshold": 5,   "window_seconds": 86400,"action": "flag"},
            {"slug": "blocked-ip",      "name": "Blocked IP",       "rule_type": "ip_duplicate",   "severity": 3, "threshold": 1,   "window_seconds": 86400,"action": "warn"},
            {"slug": "referral-abuse",  "name": "Referral Abuse",   "rule_type": "referral_abuse", "severity": 3, "threshold": 20,  "window_seconds": 86400,"action": "suspend"},
            {"slug": "coin-velocity",   "name": "Coin Velocity",    "rule_type": "velocity_check", "severity": 3, "threshold": 10000,"window_seconds": 3600, "action": "flag"},
        ]
        for d in defaults:
            AntiCheatRule.objects.get_or_create(slug=d["slug"], defaults={**d, "is_active": True, "tenant": tenant})
