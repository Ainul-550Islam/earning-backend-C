"""
SmartLink Push Notification Traffic Router
World #1 Feature: Optimized routing for push notification traffic.

Push traffic has unique characteristics:
- Very low CR compared to search/social
- High volume, low quality
- Requires aggressive fraud filtering
- Best results with mobile-only targeting

Supports major push networks:
PropellerAds, Zeropark, RichPush, EvaDav, Adsterra
"""
import logging
from django.core.cache import cache

logger = logging.getLogger('smartlink.integrations.push')


class PushNotificationRouter:
    """
    Specialized routing logic for push notification traffic.
    Automatically applies push-optimized settings.
    """

    # Known push network user-agents and click ID params
    PUSH_NETWORKS = {
        'propellerads': {
            'click_id_param': 'clickid',
            'sub_mapping':    {'sub1': 'clickid', 'sub2': 'zoneid'},
        },
        'zeropark': {
            'click_id_param': 'zp_ckid',
            'sub_mapping':    {'sub1': 'zp_ckid', 'sub2': 'keyword'},
        },
        'richadz': {
            'click_id_param': 'aff_click_id',
            'sub_mapping':    {'sub1': 'aff_click_id'},
        },
        'evadav': {
            'click_id_param': 'click_id',
            'sub_mapping':    {'sub1': 'click_id', 'sub2': 'site_id'},
        },
        'adsterra': {
            'click_id_param': '_trk',
            'sub_mapping':    {'sub1': '_trk'},
        },
    }

    def detect_push_network(self, query_params: dict) -> str | None:
        """Detect which push network this click came from."""
        for network, config in self.PUSH_NETWORKS.items():
            click_param = config['click_id_param']
            if click_param in query_params:
                return network
        return None

    def extract_push_sub_ids(self, network: str, query_params: dict) -> dict:
        """
        Extract sub IDs from push network click parameters.
        Automatically maps network-specific params to sub1-sub5.
        """
        config = self.PUSH_NETWORKS.get(network, {})
        mapping = config.get('sub_mapping', {})

        sub_ids = {'sub1': '', 'sub2': '', 'sub3': '', 'sub4': '', 'sub5': ''}
        for sub_key, param_name in mapping.items():
            value = query_params.get(param_name, '')
            if value:
                sub_ids[sub_key] = str(value)[:255]

        return sub_ids

    def apply_push_fraud_thresholds(self, fraud_score: int) -> str:
        """
        Push traffic has lower quality baseline — adjust thresholds.
        Push: block at 70+ (vs 85 for regular traffic).
        """
        if fraud_score >= 70:
            return 'block'
        if fraud_score >= 45:
            return 'flag'
        return 'allow'

    def get_push_rotation_config(self) -> dict:
        """
        Recommended rotation config for push traffic.
        Push converts better with EPC-optimized rotation.
        """
        return {
            'rotation_method':    'epc_optimized',
            'auto_optimize_epc':  True,
            'optimization_interval_minutes': 15,  # More frequent for push
        }

    def build_push_postback_url(self, network: str, base_url: str,
                                  click_id: str, payout: float) -> str:
        """Build network-specific postback URL."""
        from ...utils import build_tracking_url
        config   = self.PUSH_NETWORKS.get(network, {})
        click_param = config.get('click_id_param', 'click_id')

        params = {
            click_param: click_id,
            'payout':     str(payout),
            'status':     'approved',
        }
        return build_tracking_url(base_url, params)
