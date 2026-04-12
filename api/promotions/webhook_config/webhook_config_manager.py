# =============================================================================
# promotions/webhook_config/webhook_config_manager.py
# Webhook Configuration — Publisher sets S2S postback URLs, events
# =============================================================================
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

WEBHOOK_EVENTS = {
    'submission.approved': 'Fires when a task is approved',
    'submission.rejected': 'Fires when a task is rejected',
    'payout.processed':    'Fires when payout is sent',
    'fraud.detected':      'Fires when fraud is detected',
    'milestone.achieved':  'Fires when milestone is reached',
    'referral.converted':  'Fires when a referred user converts',
}

POSTBACK_MACROS = {
    '{click_id}':    'Unique click/tracking ID',
    '{user_id}':     'Publisher user ID',
    '{offer_id}':    'Campaign/offer ID',
    '{payout}':      'Commission amount in USD',
    '{currency}':    'Always USD',
    '{status}':      'approved / rejected',
    '{country}':     'User country code (US, GB, etc.)',
    '{s1}':          'SubID slot 1',
    '{s2}':          'SubID slot 2',
    '{s3}':          'SubID slot 3',
    '{timestamp}':   'Unix timestamp',
}


class WebhookConfigManager:
    WH_PREFIX = 'webhook_config:'

    def set_postback_url(self, publisher_id: int, event: str, url: str,
                          method: str = 'GET', secret: str = '') -> dict:
        if event not in WEBHOOK_EVENTS:
            return {'error': f'Invalid event. Available: {", ".join(WEBHOOK_EVENTS.keys())}'}
        config = cache.get(f'{self.WH_PREFIX}{publisher_id}', {})
        config[event] = {
            'url': url,
            'method': method,
            'secret': secret,
            'is_active': True,
            'last_fired': None,
            'total_fires': 0,
            'last_response_code': None,
            'configured_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.WH_PREFIX}{publisher_id}', config, timeout=3600 * 24 * 365)
        return {
            'event': event,
            'event_description': WEBHOOK_EVENTS[event],
            'url': url,
            'method': method,
            'available_macros': POSTBACK_MACROS,
            'status': 'configured',
        }

    def get_publisher_webhooks(self, publisher_id: int) -> dict:
        config = cache.get(f'{self.WH_PREFIX}{publisher_id}', {})
        result = {}
        for event, desc in WEBHOOK_EVENTS.items():
            if event in config:
                result[event] = {
                    'configured': True,
                    'url': config[event]['url'],
                    'method': config[event]['method'],
                    'is_active': config[event]['is_active'],
                    'last_fired': config[event].get('last_fired'),
                    'total_fires': config[event].get('total_fires', 0),
                    'description': desc,
                }
            else:
                result[event] = {'configured': False, 'description': desc}
        return result

    def fire_webhook(self, publisher_id: int, event: str, payload: dict) -> dict:
        """Fire a configured webhook."""
        config = cache.get(f'{self.WH_PREFIX}{publisher_id}', {})
        if event not in config or not config[event].get('is_active'):
            return {'fired': False, 'reason': 'not_configured'}
        import urllib.request, urllib.parse, json
        wh = config[event]
        url = wh['url']
        for macro, value in payload.items():
            url = url.replace(f'{{{macro}}}', str(value))
        try:
            if wh['method'] == 'POST':
                data = json.dumps(payload).encode()
                req = urllib.request.Request(url, data=data,
                    headers={'Content-Type': 'application/json', 'User-Agent': 'YourPlatform-Webhook/1.0'})
            else:
                req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                wh['last_response_code'] = resp.status
        except Exception as e:
            wh['last_response_code'] = 0
        wh['last_fired'] = timezone.now().isoformat()
        wh['total_fires'] = wh.get('total_fires', 0) + 1
        config[event] = wh
        cache.set(f'{self.WH_PREFIX}{publisher_id}', config, timeout=3600 * 24 * 365)
        return {'fired': True, 'event': event, 'response_code': wh['last_response_code']}

    def get_available_events(self) -> dict:
        return {event: {'description': desc, 'macros': list(POSTBACK_MACROS.keys())}
                for event, desc in WEBHOOK_EVENTS.items()}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_webhook_view(request):
    manager = WebhookConfigManager()
    result = manager.set_postback_url(
        publisher_id=request.user.id,
        event=request.data.get('event', ''),
        url=request.data.get('url', ''),
        method=request.data.get('method', 'GET'),
        secret=request.data.get('secret', ''),
    )
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_webhooks_view(request):
    manager = WebhookConfigManager()
    return Response(manager.get_publisher_webhooks(request.user.id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def webhook_events_view(request):
    manager = WebhookConfigManager()
    return Response({'events': manager.get_available_events(), 'macros': POSTBACK_MACROS})
