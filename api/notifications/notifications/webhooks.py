# earning_backend/api/notifications/webhooks.py
"""
Webhooks — Inbound webhook views and processors for notification system.
"""
import hashlib, hmac, json, logging, uuid
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def _verify_signature(payload: bytes, sig: str, secret: str, algo: str = 'sha256') -> bool:
    if not secret:
        return not getattr(settings, 'WEBHOOK_REQUIRE_SIGNATURE', True)
    h = hmac.new(secret.encode(), payload, getattr(hashlib, algo, hashlib.sha256))
    return hmac.compare_digest(h.hexdigest(), sig)


@csrf_exempt
@require_http_methods(['POST'])
def sendgrid_webhook(request):
    """Receive SendGrid email event webhooks."""
    sig = request.headers.get('X-Twilio-Email-Event-Webhook-Signature', '')
    if sig and not _verify_signature(request.body, sig, getattr(settings, 'SENDGRID_WEBHOOK_KEY', '')):
        return HttpResponse('Unauthorized', status=401)
    try:
        events = json.loads(request.body)
        from api.notifications.tasks.delivery_tracking_tasks import process_sendgrid_events_task
        process_sendgrid_events_task.delay(events if isinstance(events, list) else [events])
        return HttpResponse(status=200)
    except Exception as exc:
        logger.error(f'sendgrid_webhook: {exc}')
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def twilio_sms_webhook(request):
    """Receive Twilio SMS status callback webhooks."""
    try:
        if getattr(settings, 'TWILIO_AUTH_TOKEN', ''):
            sig = request.headers.get('X-Twilio-Signature', '')
            from twilio.request_validator import RequestValidator
            if not RequestValidator(settings.TWILIO_AUTH_TOKEN).validate(
                request.build_absolute_uri(), dict(request.POST), sig
            ):
                return HttpResponse('Unauthorized', status=401)
    except ImportError:
        pass
    except Exception:
        pass
    try:
        data = {k: v[0] if isinstance(v, list) else v for k, v in dict(request.POST).items()}
        from api.notifications.tasks.delivery_tracking_tasks import process_twilio_webhook_task
        process_twilio_webhook_task.delay(data)
        return HttpResponse(status=200)
    except Exception as exc:
        logger.error(f'twilio_sms_webhook: {exc}')
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def one_click_unsubscribe(request, token: str):
    """One-click email unsubscribe (RFC 8058 List-Unsubscribe-Post)."""
    try:
        from api.notifications.tasks.unsubscribe_tasks import process_one_click_unsubscribe_task
        process_one_click_unsubscribe_task.delay(token)
        if request.method == 'POST':
            return JsonResponse({'success': True, 'message': 'Unsubscribed successfully.'})
        return JsonResponse({'success': True, 'message': 'Unsubscribed successfully.'})
    except Exception as exc:
        logger.error(f'one_click_unsubscribe: {exc}')
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
@require_http_methods(['GET'])
def vapid_public_key(request):
    """Return VAPID public key for browser push subscription setup."""
    try:
        from api.notifications.services.providers.WebPushProvider import web_push_provider
        return JsonResponse({'vapid_public_key': web_push_provider.get_vapid_public_key()})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def fcm_delivery_receipt(request):
    """Handle FCM delivery receipt callbacks."""
    try:
        data = json.loads(request.body)
        msg_id = data.get('message_id', '')
        status = data.get('delivery_status', '')
        logger.debug(f'FCM receipt: {msg_id} → {status}')
        return HttpResponse(status=200)
    except Exception as exc:
        logger.error(f'fcm_delivery_receipt: {exc}')
        return JsonResponse({'error': str(exc)}, status=400)
