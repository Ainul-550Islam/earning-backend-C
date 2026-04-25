# api/payment_gateways/affiliate_tools.py
# Affiliate marketing tools — deep links, creatives, tracking pixels
import logging
from django.conf import settings
logger=logging.getLogger(__name__)
BASE_URL=getattr(settings,'SITE_URL','https://yourdomain.com')

class AffiliateToolsService:
    def generate_tracking_link(self,offer,publisher,sub1='',sub2='',sub3=''):
        params=f'?aff_id={publisher.id}&offer_id={offer.id}'
        if sub1: params+=f'&sub1={sub1}'
        if sub2: params+=f'&sub2={sub2}'
        if sub3: params+=f'&sub3={sub3}'
        return f'{BASE_URL}/api/payment/tracking/click/{params}'
    def get_creatives(self,offer):
        try:
            from api.payment_gateways.offers.models import OfferCreative
            return list(OfferCreative.objects.filter(offer=offer,is_active=True).values('id','creative_type','title','file_url','dimensions','click_url'))
        except: return []
    def get_publisher_tools_summary(self,publisher):
        try:
            from api.payment_gateways.smartlink.models import SmartLink
            from api.payment_gateways.locker.models import ContentLocker
            from api.payment_gateways.tracking.models import Click
            return {
                'smartlinks':SmartLink.objects.filter(publisher=publisher,status='active').count(),
                'lockers':ContentLocker.objects.filter(publisher=publisher,status='active').count(),
                'total_clicks':Click.objects.filter(publisher=publisher).count(),
                'tracking_link':f'{BASE_URL}/api/payment/tracking/click/?aff_id={publisher.id}',
                'postback_url':f'{BASE_URL}/api/payment/tracking/postback/?click_id={{click_id}}&payout={{payout}}&status=approved',
            }
        except Exception as e: return {'error':str(e)}
    def validate_postback_url(self,url):
        import re
        if not url: return False,'URL is required'
        if not url.startswith('http'): return False,'URL must start with http:// or https://'
        if len(url)>2000: return False,'URL too long'
        if '{click_id}' not in url and 'click_id' not in url: return False,'URL must contain click_id macro'
        return True,''
affiliate_tools=AffiliateToolsService()
