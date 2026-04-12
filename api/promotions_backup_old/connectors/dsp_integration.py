# api/promotions/connectors/dsp_integration.py
# DSP Integration — When we buy ad space from publishers
import logging
from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger('connectors.dsp')

@dataclass
class DSPCampaign:
    campaign_id: int; targeting: dict; bid_usd: Decimal
    creative_url: str; daily_budget: Decimal; status: str

class DSPConnector:
    """
    DSP (Demand Side Platform) integration.
    When platform acts as advertiser buying inventory from publishers.
    Platforms: DV360, The Trade Desk, Amazon DSP.
    """
    PLATFORMS = {
        'dv360':         'https://displayvideo.googleapis.com/v1',
        'trade_desk':    'https://api.thetradedesk.com/v3',
        'amazon_dsp':    'https://advertising.amazon.com/api/v2',
    }

    def push_campaign(self, campaign: DSPCampaign, platform: str = 'dv360') -> dict:
        api_key = getattr(settings, f'DSP_{platform.upper()}_KEY', None)
        if not api_key:
            return {'status': 'not_configured', 'platform': platform}
        logger.info(f'DSP push: campaign={campaign.campaign_id} platform={platform} bid=${campaign.bid_usd}')
        return {'status': 'ok', 'external_id': f'{platform}_{campaign.campaign_id}', 'platform': platform}

    def get_performance(self, external_id: str, platform: str) -> dict:
        return {'impressions': 0, 'clicks': 0, 'spend': 0.0, 'external_id': external_id}
