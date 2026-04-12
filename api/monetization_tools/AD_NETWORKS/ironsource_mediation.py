"""AD_NETWORKS/ironsource_mediation.py — IronSource mediation layer."""
import logging
from ..models import AdNetwork, WaterfallConfig

logger = logging.getLogger(__name__)

class IronSourceMediationLayer:
    """Manages IronSource as mediation platform across multiple ad sources."""

    def __init__(self, network: AdNetwork):
        self.network = network

    def get_mediated_networks(self, ad_unit_id: int) -> list:
        """Return all active mediated networks for an ad unit via IronSource."""
        return list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, is_active=True
            ).select_related("ad_network").order_by("priority")
        )

    def select_winner(self, bids: list) -> dict:
        """Select highest bid from IronSource mediation auction."""
        if not bids:
            return {}
        return max(bids, key=lambda b: float(b.get("cpm", 0)))

    def build_init_config(self) -> dict:
        return {
            "appKey":      self.network.app_id or "",
            "adSources":   [],
            "timeout":     self.network.timeout_ms,
        }
