# =============================================================================
# promotions/postback_tools/postback_tester.py
# Postback Tester — Send test postback to verify advertiser setup
# "The Complete Beginner's Guide to Postback Tracking" — CPAlead Blog
# =============================================================================
import urllib.request
import urllib.parse
import json
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid, logging

logger = logging.getLogger(__name__)

TEST_POSTBACK_PARAMS = {
    'click_id':    'TEST_CLICK_{uuid}',
    'offer_id':    'TEST_OFFER_001',
    'payout':      '1.00',
    'currency':    'USD',
    'status':      'approved',
    'country':     'US',
    'timestamp':   '{ts}',
}


class PostbackTester:
    """Send test S2S postbacks to verify integration."""
    LOG_PREFIX = 'postback_log:'

    def send_test_postback(
        self,
        postback_url: str,
        publisher_id: int,
        custom_params: dict = None,
        method: str = 'GET',
    ) -> dict:
        """Send a test postback to verify URL works."""
        test_id = str(uuid.uuid4())[:8].upper()
        params = {**TEST_POSTBACK_PARAMS}
        params['click_id'] = f'TEST_CLICK_{test_id}'
        params['timestamp'] = str(int(timezone.now().timestamp()))
        if custom_params:
            params.update(custom_params)

        # Build URL with params
        full_url = f'{postback_url}?{urllib.parse.urlencode(params)}'

        result = {
            'test_id': test_id,
            'postback_url': postback_url,
            'full_url': full_url,
            'params_sent': params,
            'method': method,
            'sent_at': timezone.now().isoformat(),
        }

        try:
            req = urllib.request.Request(full_url, method=method)
            req.add_header('User-Agent', 'YourPlatform-PostbackTester/1.0')
            with urllib.request.urlopen(req, timeout=10) as resp:
                response_body = resp.read()[:500].decode('utf-8', errors='ignore')
                result.update({
                    'success': True,
                    'http_status': resp.status,
                    'response_body': response_body,
                    'response_time_ms': 0,
                })
        except urllib.error.HTTPError as e:
            result.update({'success': False, 'http_status': e.code, 'error': str(e)})
        except Exception as e:
            result.update({'success': False, 'http_status': 0, 'error': str(e)})

        # Log result
        log_key = f'{self.LOG_PREFIX}{publisher_id}'
        logs = cache.get(log_key, [])
        logs.insert(0, result)
        cache.set(log_key, logs[:50], timeout=3600 * 24 * 7)

        logger.info(f'Postback test: pub={publisher_id} url={postback_url[:50]} success={result.get("success")}')
        return result

    def get_postback_logs(self, publisher_id: int) -> list:
        """Get recent postback test logs."""
        return cache.get(f'{self.LOG_PREFIX}{publisher_id}', [])

    def validate_postback_url(self, url: str) -> dict:
        """Validate postback URL format before testing."""
        issues = []
        if not url.startswith(('http://', 'https://')):
            issues.append('URL must start with http:// or https://')
        if len(url) > 2000:
            issues.append('URL too long (max 2000 chars)')
        if ' ' in url:
            issues.append('URL cannot contain spaces')
        macros_detected = []
        common_macros = ['{click_id}', '{payout}', '{status}', '{{click_id}}', '{CLICK_ID}']
        for macro in common_macros:
            if macro.lower() in url.lower():
                macros_detected.append(macro)
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'macros_detected': macros_detected,
            'url': url,
            'suggestion': (
                'Add ?click_id={click_id}&payout={payout}&status={status} to your URL'
                if not macros_detected else 'URL looks good!'
            ),
        }

    def generate_postback_url_template(self, platform: str = 'custom') -> dict:
        """Generate postback URL template for common platforms."""
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        templates = {
            'custom':      f'{base}/api/promotions/postback/?click_id={{click_id}}&payout={{payout}}&status={{status}}',
            'appsflyer':   f'{base}/api/promotions/postback/appsflyer/?clickid={{{{af_click_id}}}}&payout={{payout}}',
            'adjust':      f'{base}/api/promotions/postback/adjust/?adid={{{{adid}}}}&payout={{payout}}',
            'hasoffers':   f'{base}/api/promotions/postback/?click_id={{{{transaction_id}}}}&payout={{{{payout}}}}',
            'voluum':      f'{base}/api/promotions/postback/?click_id={{{{clickid}}}}&payout={{{{payout}}}}',
        }
        return {
            'platform': platform,
            'template_url': templates.get(platform, templates['custom']),
            'available_macros': {
                '{click_id}': 'Unique click identifier',
                '{payout}': 'Commission amount in USD',
                '{status}': 'approved / rejected',
                '{offer_id}': 'Campaign/offer ID',
                '{country}': 'User country (2-letter ISO)',
                '{sub_id}': 'Publisher SubID parameter',
            },
        }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_postback_view(request):
    """POST /api/promotions/postback-tools/test/"""
    tester = PostbackTester()
    url = request.data.get('postback_url', '')
    validation = tester.validate_postback_url(url)
    if not validation['valid']:
        return Response({'error': 'Invalid URL', 'issues': validation['issues']}, status=status.HTTP_400_BAD_REQUEST)
    result = tester.send_test_postback(
        postback_url=url,
        publisher_id=request.user.id,
        custom_params=request.data.get('custom_params', {}),
        method=request.data.get('method', 'GET'),
    )
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def postback_logs_view(request):
    """GET /api/promotions/postback-tools/logs/"""
    tester = PostbackTester()
    return Response({'logs': tester.get_postback_logs(request.user.id)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def postback_template_view(request):
    """GET /api/promotions/postback-tools/template/?platform=appsflyer"""
    tester = PostbackTester()
    platform = request.query_params.get('platform', 'custom')
    return Response(tester.generate_postback_url_template(platform))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_postback_url_view(request):
    """POST /api/promotions/postback-tools/validate/"""
    tester = PostbackTester()
    return Response(tester.validate_postback_url(request.data.get('url', '')))
