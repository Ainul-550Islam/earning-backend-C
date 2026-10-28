# engagement/services/campaign_service.py
import hashlib
import logging
from django.utils import timezone
from ..models.campaign import (UserSegment, SegmentMember, Campaign, CampaignEvent,
                                FeatureFlag, ABTest, ABTestVariant, UserABAssignment)

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """Check if a feature is enabled for a user."""

    @staticmethod
    def is_enabled(user, flag_slug: str) -> bool:
        try:
            flag = FeatureFlag.objects.get(slug=flag_slug, is_enabled=True)
        except FeatureFlag.DoesNotExist:
            return False

        # 100% rollout → always enabled
        if flag.rollout_pct >= 100:
            return True
        # 0% → always disabled
        if flag.rollout_pct <= 0:
            return False

        # Deterministic bucket assignment based on user PK
        bucket = int(hashlib.md5(f"{flag_slug}:{user.pk}".encode()).hexdigest(), 16) % 100
        return bucket < flag.rollout_pct

    @staticmethod
    def get_config(flag_slug: str) -> dict:
        try:
            flag = FeatureFlag.objects.get(slug=flag_slug)
            return flag.config
        except FeatureFlag.DoesNotExist:
            return {}


class ABTestService:
    """Assign users to A/B variants and track conversions."""

    @classmethod
    def get_variant(cls, user, test_slug: str) -> "ABTestVariant | None":
        """Get (or create) a user's variant assignment for a test."""
        try:
            test = ABTest.objects.get(slug=test_slug, status="running")
        except ABTest.DoesNotExist:
            return None

        existing = UserABAssignment.objects.filter(user=user, test=test).select_related("variant").first()
        if existing:
            return existing.variant

        return cls._assign(user, test)

    @classmethod
    def track_conversion(cls, user, test_slug: str):
        try:
            test    = ABTest.objects.get(slug=test_slug, status="running")
            assign  = UserABAssignment.objects.get(user=user, test=test)
            ABTestVariant.objects.filter(pk=assign.variant_id).update(
                conversion_count=__import__("django.db.models", fromlist=["F"]).F("conversion_count") + 1
            )
        except Exception as exc:
            logger.debug("ABTestService.track_conversion: %s", exc)

    @classmethod
    def _assign(cls, user, test: ABTest) -> "ABTestVariant | None":
        from django.db import transaction
        variants = list(ABTestVariant.objects.filter(test=test).order_by("slug"))
        if not variants:
            return None

        # Weighted random assignment
        total = sum(v.traffic_pct for v in variants)
        bucket = int(hashlib.md5(f"{test.slug}:{user.pk}".encode()).hexdigest(), 16) % total
        cumulative = 0
        chosen = variants[-1]
        for v in variants:
            cumulative += v.traffic_pct
            if bucket < cumulative:
                chosen = v
                break

        with transaction.atomic():
            UserABAssignment.objects.get_or_create(user=user, test=test, defaults={"variant": chosen})
            ABTestVariant.objects.filter(pk=chosen.pk).update(
                participant_count=__import__("django.db.models", fromlist=["F"]).F("participant_count") + 1
            )
        return chosen


class CampaignService:
    """Evaluate and deliver campaigns to users."""

    @classmethod
    def deliver(cls, campaign: Campaign, tenant=None):
        """Deliver a campaign to its target segment. Called by Celery."""
        from ..services.notification_service import NotificationService
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if campaign.status != "scheduled":
            return 0

        segment = campaign.target_segment
        if segment:
            user_ids = SegmentMember.objects.filter(segment=segment).values_list("user_id", flat=True)
            users    = User.objects.filter(pk__in=user_ids, is_active=True)
        else:
            users = User.objects.filter(is_active=True)

        config  = campaign.config
        title   = config.get("title", campaign.name)
        body    = config.get("body", "")
        count   = 0

        for user in users.iterator(chunk_size=200):
            CampaignEvent.objects.get_or_create(campaign=campaign, user=user, event="reach")
            NotificationService.send(user, "reward", title=title, body=body,
                                     data={"campaign_id": campaign.pk}, tenant=tenant)
            count += 1

        campaign.reach_count = count
        campaign.status      = "running"
        campaign.save(update_fields=["reach_count", "status"])
        logger.info("CampaignService: delivered campaign=%s to %d users", campaign.slug, count)
        return count

    @classmethod
    def track_conversion(cls, user, campaign_id: int):
        try:
            campaign = Campaign.objects.get(pk=campaign_id)
            obj, created = CampaignEvent.objects.get_or_create(campaign=campaign, user=user, event="convert")
            if created:
                Campaign.objects.filter(pk=campaign_id).update(
                    conversion_count=__import__("django.db.models", fromlist=["F"]).F("conversion_count") + 1
                )
        except Exception as exc:
            logger.debug("CampaignService.track_conversion: %s", exc)

    @classmethod
    def list_campaigns(cls, tenant=None) -> list:
        qs = Campaign.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("-created_at")[:100])

    @classmethod
    def get_campaign(cls, campaign_id: int) -> "Campaign":
        return Campaign.objects.get(pk=campaign_id)

    @classmethod
    def create_campaign(cls, data: dict, tenant=None) -> "Campaign":
        from django.utils import timezone
        return Campaign.objects.create(
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=data.get("status", "draft"),
            starts_at=data.get("starts_at", timezone.now()),
            ends_at=data.get("ends_at", timezone.now()),
            tenant=tenant,
        )

    @classmethod
    def update_campaign(cls, campaign_id: int, data: dict) -> "Campaign":
        allowed = {"name", "description", "status", "starts_at", "ends_at"}
        update_data = {k: v for k, v in data.items() if k in allowed}
        Campaign.objects.filter(pk=campaign_id).update(**update_data)
        return Campaign.objects.get(pk=campaign_id)

    @classmethod
    def delete_campaign(cls, campaign_id: int) -> None:
        Campaign.objects.filter(pk=campaign_id).delete()


class SegmentService:
    """Sync dynamic segment membership."""

    @classmethod
    def sync_segment(cls, segment: UserSegment, tenant=None):
        """Recompute who is in this segment and update SegmentMember rows."""
        from django.contrib.auth import get_user_model
        from datetime import timedelta, date
        User = get_user_model()

        criteria = segment.criteria
        users    = []

        if criteria == "all":
            users = User.objects.filter(is_active=True)
        elif criteria == "new":
            cutoff = timezone.now() - timedelta(days=7)
            users  = User.objects.filter(is_active=True, date_joined__gte=cutoff)
        elif criteria == "at_risk":
            from ..models.checkin import DailyCheckIn
            checked_recently = DailyCheckIn.objects.filter(
                date__gte=date.today() - timedelta(days=3)
            ).values_list("user_id", flat=True)
            users = User.objects.filter(is_active=True).exclude(pk__in=checked_recently)
        elif criteria == "premium":
            from ..models.battle_pass import UserBattlePass
            premium_ids = UserBattlePass.objects.filter(is_premium=True).values_list("user_id", flat=True)
            users = User.objects.filter(pk__in=premium_ids, is_active=True)
        elif criteria == "guild_member":
            from ..models.guild import GuildMember
            guild_ids = GuildMember.objects.filter(status="active").values_list("user_id", flat=True)
            users = User.objects.filter(pk__in=guild_ids, is_active=True)
        else:
            users = User.objects.filter(is_active=True)

        SegmentMember.objects.filter(segment=segment).delete()
        SegmentMember.objects.bulk_create([
            SegmentMember(segment=segment, user=u, tenant=tenant)
            for u in users
        ], ignore_conflicts=True)

        segment.member_count = users.count() if hasattr(users, "count") else len(list(users))
        segment.last_synced  = timezone.now()
        segment.save(update_fields=["member_count", "last_synced"])
        return segment.member_count
