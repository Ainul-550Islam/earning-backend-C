from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.rotate_inventory')

class Command(BaseCommand):
    help = 'Rotate ad inventory — refresh slot assignments and fill rates'

    def handle(self, *args, **options):
        from api.promotions.inventory.slot_config import SlotConfigManager
        from api.promotions.inventory.ad_rotation import AdRotationEngine, RotationStrategy
        from api.promotions.models import Campaign, AdSlot
        from api.promotions.choices import CampaignStatus

        slots    = SlotConfigManager().get_available_slots()
        rotated  = unfilled = 0

        for slot in slots:
            active_camps = Campaign.objects.filter(
                status=CampaignStatus.ACTIVE,
                platform__name__iexact=slot.platform
            ).values('id','bid_amount_usd')[:20]

            pool = [{'id': c['id'], 'bid': float(c['bid_amount_usd'])} for c in active_camps]
            if pool:
                result = AdRotationEngine().select_ad(slot.slot_id, pool, RotationStrategy.WEIGHTED)
                if result: rotated += 1
            else:
                unfilled += 1

        self.stdout.write(self.style.SUCCESS(f'Inventory rotated: {rotated} filled, {unfilled} unfilled'))
