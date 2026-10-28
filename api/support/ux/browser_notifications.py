"""api/support/ux/browser_notifications.py FILE 15"""
import json, logging
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
logger = logging.getLogger(__name__)

class BrowserNotificationSystem:
    VAPID_PUBLIC  = getattr(settings, "VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE = getattr(settings, "VAPID_PRIVATE_KEY", "")
    VAPID_EMAIL   = getattr(settings, "VAPID_EMAIL", "support@yoursite.com")

    def save_subscription(self, user, data: dict) -> bool:
        try:
            from api.support.ux.models import BrowserPushSubscription
            BrowserPushSubscription.objects.update_or_create(
                user=user, endpoint=data.get("endpoint",""),
                defaults={"subscription_data":json.dumps(data),"is_active":True})
            return True
        except Exception as e: logger.error(f"Save push sub: {e}"); return False

    def send(self, user, title: str, body: str, data: dict = None) -> bool:
        if not self.VAPID_PRIVATE: return False
        try:
            from pywebpush import webpush, WebPushException
            from api.support.ux.models import BrowserPushSubscription
            sent = 0
            for sub in BrowserPushSubscription.objects.filter(user=user,is_active=True):
                try:
                    webpush(subscription_info=json.loads(sub.subscription_data),
                        data=json.dumps({"title":title,"body":body,"data":data or {}}),
                        vapid_private_key=self.VAPID_PRIVATE,
                        vapid_claims={"sub":f"mailto:{self.VAPID_EMAIL}"})
                    sent += 1
                except WebPushException as e:
                    if e.response and e.response.status_code == 410: sub.is_active=False; sub.save()
            return sent > 0
        except ImportError: logger.warning("pip install pywebpush"); return False
        except Exception as e: logger.error(f"Browser push: {e}"); return False

    def notify_ticket_reply(self, ticket) -> bool:
        return self.send(ticket.user,f"New Reply #{ticket.ticket_id}","Support team replied.",{"type":"ticket_reply","ticket_id":ticket.ticket_id})

browser_notifications = BrowserNotificationSystem()

@api_view(["POST"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def save_push_subscription(request):
    ok = browser_notifications.save_subscription(request.user, request.data)
    return Response({"success":ok,"vapid_public":browser_notifications.VAPID_PUBLIC})
@permission_classes([IsAuthenticated])
def get_vapid_key(request):
    return Response({"vapid_public_key":browser_notifications.VAPID_PUBLIC})