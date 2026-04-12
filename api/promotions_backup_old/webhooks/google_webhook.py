# api/promotions/webhooks/google_webhook.py
# Google Play + Google Ads webhook/notification handler
import hashlib, json, logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
logger = logging.getLogger('webhooks.google')

@csrf_exempt
@require_POST
def google_play_notification_view(request):
    """Google Play Real-time Developer Notifications (RTDN) — Pub/Sub push।"""
    try:
        payload = json.loads(request.body)
        message = payload.get('message', {})
        import base64
        data    = json.loads(base64.b64decode(message.get('data', '')))
    except Exception as e:
        logger.error(f'Google Play notification parse failed: {e}')
        return HttpResponse(status=400)

    handler = GooglePlayNotificationHandler()
    notif_type = data.get('notificationType')

    if 'subscriptionNotification' in data:
        handler.handle_subscription(data['subscriptionNotification'])
    elif 'oneTimeProductNotification' in data:
        handler.handle_one_time_purchase(data['oneTimeProductNotification'])
    elif 'voidedPurchaseNotification' in data:
        handler.handle_voided_purchase(data['voidedPurchaseNotification'])

    return JsonResponse({'received': True})


@csrf_exempt
@require_POST
def google_ads_conversion_view(request):
    """Google Ads conversion upload — offline conversion tracking।"""
    try:
        data = json.loads(request.body)
    except Exception:
        return HttpResponse(status=400)

    click_id    = data.get('gclid') or data.get('wbraid') or data.get('gbraid')
    conversion  = data.get('conversion_action')
    value       = data.get('conversion_value', 0)

    if click_id:
        logger.info(f'Google Ads conversion: gclid={click_id[:20]}... action={conversion} value=${value}')
        _process_gads_conversion(click_id, conversion, float(value))

    return JsonResponse({'status': 'ok'})


class GooglePlayNotificationHandler:
    def handle_subscription(self, notif: dict):
        purchase_token = notif.get('purchaseToken')
        state          = notif.get('subscriptionNotificationType')
        logger.info(f'Play subscription: token={purchase_token[:20]}... state={state}')
        # State 1 = RECOVERED, 2 = RENEWED, 12 = REVOKED, 13 = EXPIRED
        if state == 13:
            self._handle_subscription_expired(purchase_token)

    def handle_one_time_purchase(self, notif: dict):
        purchase_token = notif.get('purchaseToken')
        state          = notif.get('notificationType')
        logger.info(f'Play purchase: token={purchase_token[:20]}... state={state}')
        # State 1 = PURCHASED, 2 = CANCELED, 3 = REFUNDED
        if state == 1:
            self._handle_app_install_verified(purchase_token, notif.get('sku', ''))

    def handle_voided_purchase(self, notif: dict):
        purchase_token = notif.get('purchaseToken')
        logger.warning(f'Play voided purchase: token={purchase_token[:20]}...')
        # Find and reject related submissions
        self._void_submission(purchase_token)

    def _handle_app_install_verified(self, token: str, sku: str):
        from django.core.cache import cache
        # token → submission_id mapping lookup
        sub_id = cache.get(f'play:token:{token}')
        if sub_id:
            from api.promotions.services.task_service import TaskService
            TaskService().approve(sub_id, actor_id=0, note='verified_by_google_play')

    def _handle_subscription_expired(self, token: str):
        logger.info(f'Subscription expired: {token[:20]}...')

    def _void_submission(self, token: str):
        from django.core.cache import cache
        sub_id = cache.get(f'play:token:{token}')
        if sub_id:
            from api.promotions.services.task_service import TaskService
            TaskService().reject(sub_id, actor_id=0, reason='google_play_voided')


def _process_gads_conversion(gclid: str, conversion: str, value: float):
    from django.core.cache import cache
    click_data = cache.get(f'gads:click:{gclid}')
    if click_data and click_data.get('campaign_id'):
        from api.promotions.tracking.event_logger import EventLogger
        EventLogger().conversion(click_data['campaign_id'], click_data.get('user_id', 0), value)
