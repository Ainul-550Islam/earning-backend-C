from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.auction')

class Command(BaseCommand):
    help = 'Run scheduled auction for pending inventory slots'

    def handle(self, *args, **options):
        from api.promotions.bidding.auction_logic import AuctionEngine, AuctionSlot, Bid, AuctionType
        from api.promotions.bidding.floor_price import FloorPriceEngine
        from api.promotions.models import Campaign, AdSlot
        from api.promotions.choices import CampaignStatus
        from decimal import Decimal

        engine    = AuctionEngine()
        fp_engine = FloorPriceEngine()
        won = total = 0

        for slot in AdSlot.objects.filter(is_active=True)[:50]:
            total += 1
            floor  = fp_engine.calculate(slot.platform.name, '', 'GLOBAL')
            campaigns = Campaign.objects.filter(status=CampaignStatus.ACTIVE, platform=slot.platform).values(
                'id','advertiser_id','bid_amount_usd','spent_usd','total_budget_usd')[:20]
            bids = [
                Bid(c['id'], c['advertiser_id'], Decimal(str(c['bid_amount_usd'])),
                    0.7, None, Decimal(str(c['total_budget_usd']))-Decimal(str(c['spent_usd'])))
                for c in campaigns
            ]
            auction_slot = AuctionSlot(str(slot.id), slot.platform.name, '', 'GLOBAL', 1, 1.0, floor.floor_usd)
            result = engine.run_auction(auction_slot, bids)
            if result.winner:
                won += 1

        self.stdout.write(self.style.SUCCESS(f'Auction: {won}/{total} slots filled'))
