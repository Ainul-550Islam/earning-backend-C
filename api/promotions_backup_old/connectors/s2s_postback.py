# api/promotions/connectors/s2s_postback.py
# S2S Postback — Server-to-server conversion notification
import hashlib, hmac, logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('connectors.s2s')

class S2SPostbackHandler:
    """
    Server-to-server postback for affiliate conversions.
    Receives: advertiser sends postback when user converts.
    Sends: notify affiliate network of conversion.
    """
    def receive(self, request_data: dict, source_ip: str) -> dict:
        """Incoming S2S postback process করে।"""
        click_id    = request_data.get('click_id', '')
        payout      = request_data.get('payout', 0)
        event_name  = request_data.get('event', 'conversion')
        advertiser_id = request_data.get('advertiser_id', '')
        sig         = request_data.get('sig', '')

        # Verify signature
        if not self._verify_sig(advertiser_id, click_id, payout, sig):
            logger.warning(f'Invalid S2S signature from {source_ip}')
            return {'status': 'error', 'reason': 'invalid_signature'}

        # Process conversion
        result = self._process_conversion(click_id, float(payout), event_name)
        logger.info(f'S2S postback: click={click_id} payout=${payout} event={event_name}')
        return {'status': 'ok', **result}

    def send_postback(self, postback_url: str, params: dict) -> bool:
        """Postback URL এ notification পাঠায়।"""
        try:
            from urllib.parse import urlencode
            url  = postback_url + ('&' if '?' in postback_url else '?') + urlencode(params)
            resp = requests.get(url, timeout=10)
            logger.info(f'Postback sent: {resp.status_code} → {url[:80]}')
            return resp.status_code == 200
        except Exception as e:
            logger.error(f'Postback failed: {e}')
            return False

    def _verify_sig(self, adv_id: str, click_id: str, payout, sig: str) -> bool:
        secret = getattr(settings, f'S2S_SECRET_{adv_id}', getattr(settings, 'S2S_DEFAULT_SECRET', ''))
        if not secret: return True   # No secret configured — allow
        expected = hmac.new(secret.encode(), f'{click_id}{payout}'.encode(), hashlib.md5).hexdigest()
        return hmac.compare_digest(expected, sig)

    def _process_conversion(self, click_id: str, payout: float, event: str) -> dict:
        # Find submission by click_id and credit
        click_data = cache.get(f'track:click:{click_id}')
        if not click_data:
            return {'credited': False, 'reason': 'click_not_found'}
        try:
            from api.promotions.models import TaskSubmission
            from api.promotions.choices import SubmissionStatus
            TaskSubmission.objects.filter(
                pk=click_data.get('submission_id'), status=SubmissionStatus.PENDING
            ).update(status=SubmissionStatus.APPROVED)
            return {'credited': True, 'submission_id': click_data.get('submission_id')}
        except Exception as e:
            return {'credited': False, 'error': str(e)}
