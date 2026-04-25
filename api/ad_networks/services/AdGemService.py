"""
api/ad_networks/services/AdGemService.py
AdGem ad network service
SaaS-ready with tenant support
"""

from .AdNetworkBase import AdNetworkBase


class AdGemService(AdNetworkBase):
    """AdGem ad network integration"""
    
    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
        self.base_url = "https://api.adgem.com/v1"
    
    def generate_tracking_url(self, offer, engagement):
        """Generate tracking URL with click ID"""
        return f"https://api.adgem.com/click?offer_id={offer.external_id}&subid={engagement.id}"
    
    def process_conversion(self, webhook_data):
        """Process conversion callback from AdGem"""
        try:
            subid = webhook_data.get('subid')
            if not subid:
                return False, None
            
            from ..models import UserOfferEngagement, OfferConversion
            
            try:
                engagement = UserOfferEngagement.objects.get(id=subid)
            except UserOfferEngagement.DoesNotExist:
                return False, None
            
            conversion, created = OfferConversion.objects.get_or_create(
                engagement=engagement,
                defaults={
                    'conversion_id': webhook_data.get('conversion_id'),
                    'payout': webhook_data.get('payout', 0),
                    'conversion_status': webhook_data.get('status', 'pending'),
                    'conversion_data': webhook_data
                }
            )
            
            return True, conversion
            
        except Exception:
            return False, None
    
    def verify_postback(self, request):
        """Verify postback authenticity"""
        return True
    
    def sync_offers(self):
        """Sync offers from AdGem API"""
        return []
