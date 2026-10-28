# api/referral/services/ReferralCampaignService.py
# Campaign management: active campaigns, multipliers, auto start/end
# ============================================================

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import logging
from api.referral.models.campaign import ReferralCampaign

logger = logging.getLogger(__name__)

ACTIVE_CAMPAIGN_CACHE_KEY = 'referral_active_campaign'
CACHE_TIMEOUT = 300  # 5 minutes


class ReferralCampaignService:
    """
    ReferralCampaign lifecycle management।
    Active campaign detect করো, multiplier apply করো।
    """

    @staticmethod
    def get_active_campaign() -> 'ReferralCampaign | None':
        """
        এখন active campaign পাও।
        Cache করা থাকে।
        """
        from api.referral.models import ReferralCampaign

        cached = cache.get(ACTIVE_CAMPAIGN_CACHE_KEY)
        if cached is not None:
            return cached if cached != 'none' else None

        now = timezone.now()
        campaign = ReferralCampaign.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        ).order_by('-is_featured', '-bonus_multiplier').first()

        cache.set(
            ACTIVE_CAMPAIGN_CACHE_KEY,
            campaign if campaign else 'none',
            timeout=CACHE_TIMEOUT
        )
        return campaign

    @staticmethod
    def invalidate_campaign_cache():
        cache.delete(ACTIVE_CAMPAIGN_CACHE_KEY)
        cache.delete('referral_settings')

    @staticmethod
    def get_all_active_campaigns() -> list:
        """সব active campaigns এর list।"""
        from api.referral.models import ReferralCampaign

        now = timezone.now()
        campaigns = ReferralCampaign.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        ).order_by('-is_featured', '-bonus_multiplier')

        return [{
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'bonus_multiplier': float(c.bonus_multiplier),
            'extra_signup_bonus': float(c.extra_signup_bonus),
            'start_date': c.start_date.strftime('%Y-%m-%d %H:%M'),
            'end_date': c.end_date.strftime('%Y-%m-%d %H:%M'),
            'remaining_budget': float(c.remaining_budget()),
            'current_referrals': c.current_referrals,
            'max_referrals': c.max_referrals,
            'is_featured': c.is_featured,
        } for c in campaigns]

    @staticmethod
    @transaction.atomic
    def start_campaign(campaign_id: int) -> dict:
        """
        Campaign manually start করো।
        ReferralSettings.active_campaign update করো।
        Celery task campaign_tasks.py দিয়ে auto-start হয়।
        """
        from api.referral.models import ReferralCampaign, ReferralSettings

        try:
            campaign = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return {'success': False, 'error': 'Campaign not found'}

        campaign.is_active = True
        campaign.save(update_fields=['is_active'])

        # ReferralSettings এ active_campaign link করো
        settings = ReferralSettings.objects.first()
        if settings:
            settings.active_campaign = campaign
            settings.save(update_fields=['active_campaign'])

        ReferralCampaignService.invalidate_campaign_cache()

        logger.info(f"Campaign started: {campaign.name}")

        return {
            'success': True,
            'campaign_id': campaign.id,
            'name': campaign.name,
        }

    @staticmethod
    @transaction.atomic
    def end_campaign(campaign_id: int) -> dict:
        """
        Campaign end করো।
        ReferralSettings.active_campaign null করো।
        """
        from api.referral.models import ReferralCampaign, ReferralSettings

        try:
            campaign = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return {'success': False, 'error': 'Campaign not found'}

        campaign.is_active = False
        campaign.save(update_fields=['is_active'])

        # Settings থেকে active_campaign remove করো
        ReferralSettings.objects.filter(
            active_campaign=campaign
        ).update(active_campaign=None)

        ReferralCampaignService.invalidate_campaign_cache()

        logger.info(f"Campaign ended: {campaign.name}")

        return {'success': True, 'campaign_id': campaign.id}

    @staticmethod
    def check_and_auto_start_campaigns() -> dict:
        """
        Start date পার হয়ে গেছে এমন campaigns auto-start করো।
        Celery task দিয়ে call করা হয়।
        """
        from api.referral.models import ReferralCampaign

        now = timezone.now()

        # Should-be-active campaigns
        to_start = ReferralCampaign.objects.filter(
            is_active=False,
            start_date__lte=now,
            end_date__gte=now,
        )

        started = 0
        for campaign in to_start:
            result = ReferralCampaignService.start_campaign(campaign.id)
            if result['success']:
                started += 1

        # Should-be-ended campaigns
        to_end = ReferralCampaign.objects.filter(
            is_active=True,
            end_date__lt=now,
        )

        ended = 0
        for campaign in to_end:
            result = ReferralCampaignService.end_campaign(campaign.id)
            if result['success']:
                ended += 1

        return {'started': started, 'ended': ended}

    @staticmethod
    def apply_multiplier(
        base_amount: Decimal, campaign=None
    ) -> tuple:
        """
        Campaign multiplier apply করো।
        Returns (final_amount, multiplier_used)
        """
        if not campaign:
            campaign = ReferralCampaignService.get_active_campaign()

        if not campaign or not campaign.is_currently_active():
            return base_amount, Decimal('1')

        final = (base_amount * campaign.bonus_multiplier).quantize(
            Decimal('0.01')
        )
        return final, campaign.bonus_multiplier

    @staticmethod
    def get_campaign_performance(campaign_id: int) -> dict:
        """Campaign এর performance metrics।"""
        from api.referral.models import ReferralCampaign, ReferralEarning
        from django.db.models import Sum, Count

        try:
            campaign = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return {'error': 'Campaign not found'}

        earnings = ReferralEarning.objects.filter(
            created_at__gte=campaign.start_date,
            created_at__lte=campaign.end_date,
            campaign_multiplier__gt=1,
        ).aggregate(
            total=Sum('amount'),
            count=Count('id'),
        )

        return {
            'campaign_id': campaign.id,
            'name': campaign.name,
            'status': 'active' if campaign.is_currently_active() else 'inactive',
            'current_referrals': campaign.current_referrals,
            'max_referrals': campaign.max_referrals,
            'current_spend': float(campaign.current_spend),
            'max_budget': float(campaign.max_budget) if campaign.max_budget else None,
            'remaining_budget': float(campaign.remaining_budget()),
            'commission_paid': float(earnings['total'] or 0),
            'commission_transactions': earnings['count'] or 0,
            'days_remaining': max(
                0,
                (campaign.end_date - timezone.now()).days
            ) if campaign.is_currently_active() else 0,
        }