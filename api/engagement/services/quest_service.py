# engagement/services/quest_service.py
import logging
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from ..models.quest import Quest, UserQuest
from ..exceptions import QuestExpiredError

logger = logging.getLogger(__name__)


class QuestService:

    # ── Initialise daily / weekly quests for a user ───────────────────────────

    @classmethod
    @transaction.atomic
    def init_daily(cls, user, tenant=None):
        """Create UserQuest rows for today's active daily quests if not exists."""
        today = date.today()
        quests = Quest.objects.filter(type="daily", is_active=True)
        created = []
        for q in quests:
            uq, new = UserQuest.objects.get_or_create(
                user=user, quest=q, period_date=today,
                defaults={"tenant": tenant or getattr(user, "tenant", None)},
            )
            if new:
                created.append(uq)
        return created

    @classmethod
    @transaction.atomic
    def init_weekly(cls, user, tenant=None):
        """Create UserQuest rows for this week's active weekly quests."""
        monday = date.today() - timedelta(days=date.today().weekday())
        quests = Quest.objects.filter(type="weekly", is_active=True)
        created = []
        for q in quests:
            uq, new = UserQuest.objects.get_or_create(
                user=user, quest=q, period_date=monday,
                defaults={"tenant": tenant or getattr(user, "tenant", None)},
            )
            if new:
                created.append(uq)
        return created

    # ── Progress tracking ────────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def record_action(cls, user, action: str, increment: int = 1, tenant=None) -> list:
        """
        Record that `user` performed `action` (e.g. "spin", "checkin").
        Advances progress on matching quests; auto-completes when target met.
        Returns list of newly completed UserQuest objects.
        """
        today    = date.today()
        monday   = today - timedelta(days=today.weekday())

        active_quests = UserQuest.objects.select_for_update().filter(
            user=user,
            status="active",
            quest__action=action,
            quest__is_active=True,
        ).filter(
            # daily: period_date == today; weekly: period_date == this Monday
            period_date__in=[today, monday]
        ).select_related("quest")

        completed = []
        for uq in active_quests:
            uq.progress = min(uq.progress + increment, uq.quest.target)
            if uq.progress >= uq.quest.target:
                uq.status       = "completed"
                uq.completed_at = timezone.now()
                completed.append(uq)
            uq.save(update_fields=["progress", "status", "completed_at"])

        for uq in completed:
            cls._grant_reward(user, uq, tenant)

        return completed

    @classmethod
    @transaction.atomic
    def claim_reward(cls, user, user_quest_id: int) -> dict:
        """Manually claim reward for a completed quest (if not auto-claimed)."""
        uq = UserQuest.objects.select_for_update().get(
            pk=user_quest_id, user=user, status="completed"
        )
        if uq.reward_claimed:
            return {"already_claimed": True}
        return cls._grant_reward(user, uq, getattr(user, "tenant", None))

    # ── Private ───────────────────────────────────────────────────────────────

    @classmethod
    def _grant_reward(cls, user, uq: UserQuest, tenant=None) -> dict:
        if uq.reward_claimed:
            return {}
        q = uq.quest
        result = {}
        if q.coin_reward > 0:
            result["new_balance"] = float(CoinService.add(user, q.coin_reward, source="quest", ref_id=str(uq.pk)))
        if q.xp_reward > 0:
            result["xp"] = XPService.grant(user, q.xp_reward, source="quest", ref_id=str(uq.pk))
        uq.reward_claimed = True
        uq.save(update_fields=["reward_claimed"])
        logger.info("Quest reward claimed: user=%s quest='%s'", user.pk, q.slug)
        return result

    @staticmethod
    def active_for_user(user) -> dict:
        today  = date.today()
        monday = today - timedelta(days=today.weekday())
        daily  = UserQuest.objects.filter(user=user, period_date=today,  quest__type="daily").select_related("quest")
        weekly = UserQuest.objects.filter(user=user, period_date=monday, quest__type="weekly").select_related("quest")
        return {"daily": list(daily), "weekly": list(weekly)}
