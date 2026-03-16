from abc import ABC, abstractmethod


class AdNetworkBase(ABC):
    """Abstract base class for all ad network integrations"""
    
    @abstractmethod
    def generate_tracking_url(self, offer, engagement):
        """Generate tracking URL with click ID"""
        pass
    
    @abstractmethod
    def process_conversion(self, webhook_data):
        """Process conversion callback from ad network"""
        pass
    
    @abstractmethod
    def verify_postback(self, request):
        """Verify postback authenticity"""
        pass
    
    @abstractmethod
    def sync_offers(self):
        """Sync offers from ad network API"""
        pass
    
    def calculate_user_payout(self, network_payout, revenue_share=0.7):
        """Calculate user's payout from network payout"""
        return round(network_payout * revenue_share, 2)