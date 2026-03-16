# from .AdNetworkBase import AdNetworkBase
# from ..models import Offer, UserOfferEngagement, OfferConversion
# from django.utils import timezone


# class UnityAdsService(AdNetworkBase):
    
#     def __init__(self, ad_network):
#         self.ad_network = ad_network
#         self.api_key = ad_network.api_key
    
#     def generate_tracking_url(self, offer, engagement):
#         """Generate Unity Ads tracking URL"""
#         base_url = offer.click_url
#         params = {
#             'click_id': engagement.click_id,
#             'user_id': str(engagement.user.id),
#             'offer_id': offer.external_id,
#         }
#         query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
#         return f"{base_url}?{query_string}"
#     def process_conversion(self, webhook_data):
#     # """Process Unity Ads conversion"""
#      click_id = webhook_data.get('clickid')
#      payout = float(webhook_data.get('payout', 0))
    
#     try:
#         engagement = UserOfferEngagement.objects.get(click_id=click_id)
        
#         conversion, created = OfferConversion.objects.get_or_create(
#             engagement=engagement,
#             defaults={
#                 'postback_data': webhook_data,
#                 'payout': self.calculate_user_payout(payout),
#                 'is_verified': False
#             }
#         )
        
#         engagement.status = 'pending'
#         engagement.completed_at = timezone.now()
#         engagement.save()
        
#     return True, engagement
#     except UserOfferEngagement.DoesNotExist:
#     return False, None

# def verify_postback(self, request):
#     """Verify Unity Ads postback"""
#     # Implement Unity-specific verification
#     return True

# def sync_offers(self):
#     """Sync offers from Unity Ads API"""
#     return []

from .AdNetworkBase import AdNetworkBase
from ..models import Offer, UserOfferEngagement, OfferConversion
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class UnityAdsService(AdNetworkBase):
    
    def __init__(self, ad_network):
        self.ad_network = ad_network
        self.api_key = ad_network.api_key
    
    def generate_tracking_url(self, offer, engagement):
        """Generate Unity Ads tracking URL"""
        base_url = offer.click_url
        params = {
            'click_id': engagement.click_id,
            'user_id': str(engagement.user.id),
            'offer_id': offer.external_id,
        }
        # URL-এ ইতিমধ্যে '?' থাকলে '&' দিয়ে শুরু হবে, নাহলে '?'
        connector = '&' if '?' in base_url else '?'
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}{connector}{query_string}"

    def process_conversion(self, webhook_data):
        """Process Unity Ads conversion"""
        click_id = webhook_data.get('clickid')
        payout = float(webhook_data.get('payout', 0))
        
        try:
            engagement = UserOfferEngagement.objects.get(click_id=click_id)
            
            conversion, created = OfferConversion.objects.get_or_create(
                engagement=engagement,
                defaults={
                    'postback_data': webhook_data,
                    'payout': self.calculate_user_payout(payout),
                    'is_verified': False
                }
            )
            
            # এঙ্গেজমেন্ট স্ট্যাটাস আপডেট
            engagement.status = 'pending'
            engagement.completed_at = timezone.now()
            engagement.save()
            
            return True, engagement
            
        except UserOfferEngagement.DoesNotExist:
            logger.error(f"UnityAds: Engagement not found for click_id: {click_id}")
            return False, None
        except Exception as e:
            logger.error(f"UnityAds: Conversion error: {e}")
            return False, None

    def verify_postback(self, request):
        """Verify Unity Ads postback IP or Secret"""
        # Unity Ads সাধারণত নির্দিষ্ট IP থেকে রিকোয়েস্ট পাঠায়
        return True

    def sync_offers(self):
        """Sync offers from Unity Ads API"""
        # এখানে Unity API কল করে অফার লিস্ট রিটার্ন করতে হবে
        return []