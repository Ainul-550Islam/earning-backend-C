# api/offer_inventory/affiliate_advanced/postback_tester.py
"""Postback Tester — Test and verify S2S postback configurations."""
import logging
import uuid
from django.utils import timezone

logger = logging.getLogger(__name__)


class PostbackTester:
    """Test postback delivery and verify endpoint configurations."""

    @staticmethod
    def send_test_postback(network_id: str, user_id=None) -> dict:
        """Send a simulated test postback to verify pipeline."""
        from api.offer_inventory.models import OfferNetwork

        try:
            network = OfferNetwork.objects.get(id=network_id)
        except OfferNetwork.DoesNotExist:
            return {'success': False, 'error': 'Network not found'}

        if not network.postback_url:
            return {'success': False, 'error': 'No postback URL configured on network'}

        test_params = {
            'click_id'      : f'TEST_{uuid.uuid4().hex[:8].upper()}',
            'transaction_id': f'TEST_TX_{uuid.uuid4().hex[:8].upper()}',
            'payout'        : '0.01',
            'status'        : 'test',
            'is_test'       : 'true',
        }
        test_url = network.postback_url
        for k, v in test_params.items():
            test_url = test_url.replace(f'{{{k}}}', str(v))

        from api.offer_inventory.webhooks.s2s_postback import OutboundPostbackSender
        result = OutboundPostbackSender.send(
            url    =test_url,
            params =test_params,
            secret =network.api_secret or '',
            timeout=10,
        )
        return {
            'network'    : network.name,
            'postback_url': test_url[:150],
            'test_params': test_params,
            'result'     : result,
        }

    @staticmethod
    def verify_endpoint(endpoint_url: str, secret: str = '') -> dict:
        """Verify an S2S endpoint is responding correctly."""
        import requests, json, hmac, hashlib

        test_payload = json.dumps({
            'click_id'      : 'VERIFY_TEST',
            'transaction_id': f'VERIFY_{uuid.uuid4().hex[:6]}',
            'payout'        : '0',
            'is_test'       : 'true',
        })
        headers = {'Content-Type': 'application/json'}
        if secret:
            sig = hmac.new(secret.encode(), test_payload.encode(), hashlib.sha256).hexdigest()
            headers['X-Signature'] = f'sha256={sig}'

        try:
            resp = requests.post(endpoint_url, data=test_payload, headers=headers, timeout=10)
            return {
                'url'        : endpoint_url,
                'status_code': resp.status_code,
                'success'    : resp.status_code in (200, 201, 204),
                'latency_ms' : round(resp.elapsed.total_seconds() * 1000, 1),
                'response'   : resp.text[:200],
            }
        except Exception as e:
            return {'url': endpoint_url, 'success': False, 'error': str(e)}
