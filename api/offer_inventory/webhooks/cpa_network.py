# api/offer_inventory/webhooks/cpa_network.py
"""
CPA Network integration webhooks।
Conversion পাঠানো ও receive করার logic।
"""
import logging
import requests
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class CPANetworkWebhook:
    """Generic CPA network webhook handler।"""

    SUPPORTED_NETWORKS = {
        'maxbounty' : {'method': 'GET',  'status_field': 'status'},
        'peerfly'   : {'method': 'POST', 'status_field': 'conversion_status'},
        'clickbooth': {'method': 'GET',  'status_field': 'approved'},
        'w4'        : {'method': 'GET',  'status_field': 'status'},
        'adsempire' : {'method': 'GET',  'status_field': 'status'},
    }

    def __init__(self, network_name: str):
        self.network_name = network_name.lower()
        self.config = self.SUPPORTED_NETWORKS.get(self.network_name, {
            'method': 'GET', 'status_field': 'status'
        })

    def receive_conversion(self, params: dict) -> Optional[dict]:
        """Network থেকে incoming conversion process।"""
        try:
            click_id = (params.get('aff_sub') or params.get('sub1') or
                        params.get('click_id') or params.get('s1', ''))
            amount   = params.get('amount') or params.get('payout', 0)
            tx_id    = params.get('transaction_id') or params.get('conversion_id', '')
            status   = params.get(self.config['status_field'], 'approved')

            if not click_id:
                logger.warning(f'CPA webhook: no click_id | network={self.network_name}')
                return None

            return {
                'click_id'      : click_id,
                'transaction_id': tx_id,
                'payout'        : float(amount),
                'status'        : status,
                'network'       : self.network_name,
                'raw'           : params,
            }
        except Exception as e:
            logger.error(f'CPANetworkWebhook error: {e}')
            return None

    def fire_pixel(self, pixel_url: str, params: dict) -> bool:
        """Advertiser pixel fire।"""
        try:
            resp = requests.get(pixel_url, params=params, timeout=5)
            logger.info(f'Pixel fired: {pixel_url} → {resp.status_code}')
            return resp.status_code == 200
        except Exception as e:
            logger.error(f'Pixel fire error: {e}')
            return False

    def verify_reversal(self, params: dict) -> bool:
        """Network থেকে reversal এলে verify।"""
        reversal_fields = ['reversal', 'chargeback', 'reject', 'cancel']
        status = str(params.get('status', '')).lower()
        return any(kw in status for kw in reversal_fields)


# api/offer_inventory/webhooks/pixel_tracking.py
class PixelTracker:
    """
    Conversion pixel tracking।
    1x1 transparent GIF response + DB log।
    """

    @staticmethod
    def fire_conversion_pixel(conversion_id: str) -> bool:
        """Conversion pixel fire করো।"""
        from api.offer_inventory.models import Conversion, PixelLog
        try:
            conversion = Conversion.objects.select_related('offer').get(id=conversion_id)
            offer      = conversion.offer
            # Build pixel URL from offer's pixel config
            pixel_url  = getattr(offer, 'pixel_url', '')
            if not pixel_url:
                return True

            params = {
                'click_id'      : str(conversion.click_id),
                'transaction_id': conversion.transaction_id,
                'payout'        : str(conversion.payout_amount),
            }
            success = PixelTracker._send(pixel_url, params)
            PixelLog.objects.create(
                conversion=conversion,
                pixel_url =pixel_url,
                is_fired  =success,
            )
            return success
        except Exception as e:
            logger.error(f'Pixel tracking error: {e}')
            return False

    @staticmethod
    def _send(url: str, params: dict) -> bool:
        try:
            resp = requests.get(url, params=params, timeout=5)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    @staticmethod
    def pixel_response():
        """1x1 transparent GIF response।"""
        from django.http import HttpResponse
        gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,'
            b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        resp = HttpResponse(gif, content_type='image/gif')
        resp['Cache-Control'] = 'no-cache, no-store'
        return resp
