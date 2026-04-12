"""AD_NETWORKS/max_mediation.py — AppLovin MAX mediation."""
import logging
from decimal import Decimal
from ..models import AdNetwork, WaterfallConfig

logger = logging.getLogger(__name__)

class MAXMediationLayer:
    """AppLovin MAX mediation — bidding + waterfall hybrid."""

    def __init__(self, network: AdNetwork):
        self.network = network
        self.sdk_key = network.api_key or ""

    def get_waterfall(self, ad_unit_id: int) -> list:
        return list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, is_active=True
            ).order_by("priority")
        )

    def get_bidders(self, ad_unit_id: int) -> list:
        return list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, is_active=True, is_header_bidding=True
            ).order_by("priority")
        )

    def select_winner(self, bids: list, floor_ecpm: Decimal) -> dict:
        valid = [b for b in bids if Decimal(str(b.get("cpm", 0))) >= floor_ecpm]
        return max(valid, key=lambda b: float(b.get("cpm", 0))) if valid else {}
