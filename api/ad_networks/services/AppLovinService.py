from .AdNetworkBase import AdNetworkBase


class AppLovinService(AdNetworkBase):
    
    def __init__(self, ad_network):
        self.ad_network = ad_network
    
    def generate_tracking_url(self, offer, engagement):
        return f"{offer.click_url}?c={engagement.click_id}"
    
    def process_conversion(self, webhook_data):
        return True, None
    
    def verify_postback(self, request):
        return True
    
    def sync_offers(self):
        return []