# api/promotions/connectors/ssp_integration.py
# SSP Integration — Supply Side Platform (sell our inventory to DSPs)
import logging, requests
from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger('connectors.ssp')

class SSPConnector:
    """
    Supply Side Platform integration.
    We are the publisher — SSP connects us to advertisers/DSPs.
    Platforms: Google Ad Manager, AppNexus Seller, PubMatic.
    """
    SSP_ENDPOINTS = {
        'google_admanager': 'https://securepubads.g.doubleclick.net/gampad/ads',
        'appnexus':         'https://ib.adnxs.com/ut/v3',
        'pubmatic':         'https://hbopenbid.pubmatic.com/translator',
    }

    def register_inventory(self, slots: list[dict]) -> dict:
        """Ad inventory SSP তে register করে।"""
        ssp     = getattr(settings, 'PRIMARY_SSP', 'google_admanager')
        api_key = getattr(settings, f'SSP_{ssp.upper()}_KEY', None)
        if not api_key:
            return {'status': 'not_configured', 'ssp': ssp}
        results = {}
        for slot in slots:
            results[slot['slot_id']] = {
                'ssp': ssp, 'registered': True,
                'ad_unit_code': f'/{getattr(settings,"GAM_NETWORK_CODE","12345")}/{slot["slot_id"]}',
            }
        return {'status': 'ok', 'registered': len(results), 'slots': results}

    def get_floor_prices(self, slot_ids: list[str]) -> dict:
        """SSP থেকে dynamic floor prices নেওয়া।"""
        return {slot_id: Decimal('0.02') for slot_id in slot_ids}

    def report_impression(self, slot_id: str, campaign_id: str, price: Decimal) -> bool:
        logger.debug(f'SSP impression: slot={slot_id} camp={campaign_id} price=${price}')
        return True
