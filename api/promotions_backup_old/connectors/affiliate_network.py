# api/promotions/connectors/affiliate_network.py
# Affiliate Network — Commission Junction, ShareASale, Impact integration
import logging, requests
from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger('connectors.affiliate')

@dataclass
class AffiliateOffer:
    offer_id: str; advertiser: str; name: str
    payout_usd: Decimal; payout_type: str   # cpa, cpl, cps, cpc
    tracking_url: str; categories: list

class AffiliateNetworkConnector:
    """Multi-network affiliate offer aggregation。"""
    NETWORKS = {
        'commission_junction': 'https://commission-detail.api.cj.com/v3/publisher-affiliates',
        'shareasale':          'https://shareasale.com/x.cfm',
        'impact':              'https://api.impact.com/Mediapartners/',
    }

    def __init__(self, network: str = 'commission_junction'):
        self.network = network
        self.api_key = getattr(settings, f'AFFILIATE_{network.upper()}_KEY', '')

    def get_offers(self, category: str = None, country: str = 'US') -> list:
        if not self.api_key:
            return self._demo_offers()
        try:
            resp = requests.get(
                self.NETWORKS.get(self.network, ''),
                headers={'Authorization': f'Bearer {self.api_key}'},
                params={'categories': category, 'country': country, 'limit': 50},
                timeout=15,
            )
            return self._parse(resp.json())
        except Exception as e:
            logger.error(f'Affiliate {self.network} error: {e}')
            return []

    def _parse(self, data: dict) -> list:
        return [AffiliateOffer(
            o.get('id',''), o.get('advertiser',''), o.get('name',''),
            Decimal(str(o.get('payout',0))), o.get('type','cpa'),
            o.get('tracking_url',''), o.get('categories',[])
        ) for o in data.get('items', [])]

    def _demo_offers(self) -> list:
        return [AffiliateOffer('demo_1','Shopify','Start Free Trial',Decimal('50'),'cpa','https://shopify.com/?ref=demo',['ecommerce'])]
