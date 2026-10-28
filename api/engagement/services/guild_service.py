# engagement/services/guild_service.py
import logging
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from ..models.guild import Guild, GuildMember, GuildChallenge, GuildLeaderboard

logger = logging.getLogger(__name__)


class GuildService:

    @classmethod
    @transaction.atomic
    def create(cls, owner, name: str, slug: str, description: str = "",
               is_public: bool = True, tenant=None) -> Guild:
        guild = Guild.objects.create(
            owner=owner, name=name, slug=slug, description=description,
            is_public=is_public, tenant=tenant or getattr(owner, "tenant", None),
        )
        GuildMember.objects.create(user=owner, guild=guild, role="owner",
                                   status="active", tenant=guild.tenant)
        logger.info("GuildService: created guild=%s owner=%s", guild.name, owner.pk)
        return guild

    @classmethod
    @transaction.atomic
    def join(cls, user, guild: Guild, tenant=None) -> GuildMember:
        if GuildMember.objects.filter(user=user, guild=guild, status="active").exists():
            raise ValueError("Already a member.")
        if guild.member_count >= guild.max_members:
            raise ValueError("Guild is full.")
        from ..models.xp import UserXP
        xp_obj = XPService.get_or_create(user)
        if xp_obj.level < guild.min_level_required:
            raise ValueError(f"Minimum level {guild.min_level_required} required.")
        member = GuildMember.objects.create(
            user=user, guild=guild, role="member", status="active",
            tenant=tenant or getattr(user, "tenant", None),
        )
        logger.info("GuildService: user=%s joined guild=%s", user.pk, guild.name)
        return member

    @classmethod
    @transaction.atomic
    def leave(cls, user, guild: Guild):
        member = GuildMember.objects.get(user=user, guild=guild, status="active")
        if member.role == "owner":
            # Transfer ownership to highest-contributor admin/elder/member
            next_leader = (
                GuildMember.objects.filter(guild=guild, status="active")
                .exclude(user=user)
                .order_by("-contribution_xp")
                .first()
            )
            if next_leader:
                next_leader.role = "owner"
                next_leader.save(update_fields=["role"])
                guild.owner = next_leader.user
                guild.save(update_fields=["owner"])
            else:
                guild.is_active = False
                guild.save(update_fields=["is_active"])
        member.status = "left"
        member.save(update_fields=["status"])

    @classmethod
    @transaction.atomic
    def contribute_xp(cls, user, guild: Guild, xp_amount: int):
        """Record XP contribution to guild from a user action."""
        GuildMember.objects.filter(user=user, guild=guild, status="active").update(
            contribution_xp=__import__("django.db.models", fromlist=["F"]).F("contribution_xp") + xp_amount
        )
        Guild.objects.filter(pk=guild.pk).update(
            total_xp=__import__("django.db.models", fromlist=["F"]).F("total_xp") + xp_amount
        )

    @classmethod
    @transaction.atomic
    def advance_challenge(cls, guild: Guild, metric: str, increment: int = 1) -> bool:
        """
        Advance progress on active guild challenges matching metric.
        Returns True if any challenge completed.
        """
        now = timezone.now()
        challenges = GuildChallenge.objects.select_for_update().filter(
            guild=guild, metric=metric, is_completed=False,
            starts_at__lte=now, ends_at__gte=now,
        )
        any_completed = False
        for ch in challenges:
            ch.current = min(ch.current + increment, ch.target)
            if ch.current >= ch.target:
                ch.is_completed = True
                any_completed   = True
            ch.save(update_fields=["current", "is_completed"])
        return any_completed

    @staticmethod
    def leaderboard(week_start=None, tenant=None, limit: int = 20):
        from datetime import date, timedelta
        week_start = week_start or (date.today() - timedelta(days=date.today().weekday()))
        return list(
            GuildLeaderboard.objects.filter(week_start=week_start, tenant=tenant)
            .select_related("guild").order_by("rank")[:limit]
        )
