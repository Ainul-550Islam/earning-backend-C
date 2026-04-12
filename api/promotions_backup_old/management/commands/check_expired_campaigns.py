# api/promotions/management/commands/check_expired_campaigns.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import F, Q
import logging
logger = logging.getLogger('management.check_expired')

class Command(BaseCommand):
    help = 'Expire campaigns past end_date or budget exhausted'

    def handle(self, *args, **options):
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        from api.promotions.cache.campaign_cache import campaign_cache

        now      = timezone.now()
        expired  = Campaign.objects.filter(
            status=CampaignStatus.ACTIVE,
        ).filter(
            Q(end_date__lt=now) |
            Q(spent_usd__gte=F('total_budget_usd')) |
            Q(filled_slots__gte=F('total_slots'))
        )
        count = expired.count()
        expired.update(status=CampaignStatus.COMPLETED)

        for cid in expired.values_list('id', flat=True):
            campaign_cache.invalidate_campaign(cid)

        self.stdout.write(self.style.SUCCESS(f'Expired {count} campaigns'))
        logger.info(f'Campaign expiry check: {count} expired')
