# api/promotions/webhooks/facebook_webhook.py
# Facebook Graph API Webhook — Page events, Ad events
import hashlib, hmac, json, logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
logger = logging.getLogger('webhooks.facebook')

FB_APP_SECRET   = getattr(settings, 'FACEBOOK_APP_SECRET', '')
FB_VERIFY_TOKEN = getattr(settings, 'FACEBOOK_VERIFY_TOKEN', 'promotions_verify')

@csrf_exempt
def facebook_webhook_view(request):
    # GET = verification challenge
    if request.method == 'GET':
        mode      = request.GET.get('hub.mode')
        token     = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == FB_VERIFY_TOKEN:
            logger.info('Facebook webhook verified')
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse(status=403)

    # POST = events
    if not _verify_fb_signature(request.body, request.META.get('HTTP_X_HUB_SIGNATURE_256', '')):
        logger.warning('Invalid Facebook webhook signature')
        return HttpResponse(status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return HttpResponse(status=400)

    handler = FacebookWebhookHandler()
    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            handler.handle_change(change)
        for message in entry.get('messaging', []):
            handler.handle_message(message)

    return JsonResponse({'received': True})


class FacebookWebhookHandler:
    def handle_change(self, change: dict):
        field = change.get('field')
        value = change.get('value', {})

        if field == 'leadgen':
            self._handle_lead(value)
        elif field == 'feed':
            self._handle_feed_event(value)
        elif field == 'ad_account':
            self._handle_ad_event(value)

    def handle_message(self, msg: dict):
        sender_id = msg.get('sender', {}).get('id')
        text      = msg.get('message', {}).get('text', '')
        logger.debug(f'FB message from {sender_id}: {text[:50]}')

    def _handle_lead(self, value: dict):
        lead_id    = value.get('leadgen_id')
        page_id    = value.get('page_id')
        ad_id      = value.get('ad_id')
        logger.info(f'FB lead: lead_id={lead_id} page={page_id} ad={ad_id}')
        # Fetch lead data and create conversion
        from api.promotions.tracking.event_logger import EventLogger
        EventLogger().emit_from_dict({'event_type': 'lead', 'metadata': value}) if hasattr(EventLogger(), 'emit_from_dict') else None

    def _handle_feed_event(self, value: dict):
        item   = value.get('item')
        action = value.get('verb')
        logger.debug(f'FB feed: item={item} action={action}')
        if item == 'like' and action == 'add':
            self._process_like(value)

    def _handle_ad_event(self, value: dict):
        logger.info(f'FB ad event: {value.get("event_type")}')

    def _process_like(self, value: dict):
        from django.core.cache import cache
        page_id = value.get('post_id', '').split('_')[0]
        user_id_fb = value.get('sender_id')
        if not page_id or not user_id_fb:
            return
        # Map FB page → campaign and FB user → platform user
        mapping = cache.get(f'fb:page_campaign:{page_id}')
        if mapping:
            from api.promotions.tracking.event_logger import EventLogger
            EventLogger().impression(mapping['campaign_id'], mapping.get('user_id', 0))


def _verify_fb_signature(payload: bytes, sig_header: str) -> bool:
    if not FB_APP_SECRET:
        return True
    if not sig_header.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(FB_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)
