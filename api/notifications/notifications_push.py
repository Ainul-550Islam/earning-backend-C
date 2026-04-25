# earning_backend/api/notifications/notifications_push.py
"""Notifications Push — Push notification specific logic and helpers."""
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
logger = logging.getLogger(__name__)

def build_fcm_message(notification, token, data=None):
    from notifications.helpers import truncate, _get_sound, build_push_payload
    extra = build_push_payload(notification)
    if data:
        extra.update(data)
    priority = getattr(notification, "priority", "medium") or "medium"
    return {
        "token": token,
        "notification": {"title": truncate(notification.title,65), "body": truncate(notification.message,100)},
        "android": {"priority": "high" if priority in ("high","urgent","critical") else "normal",
                    "notification": {"icon":"ic_notification","color":"#1a73e8",
                                     "channel_id": getattr(settings,"FCM_ANDROID_CHANNEL_ID","default"),
                                     "sound": _get_sound(getattr(notification,"notification_type",""))}},
        "apns": {"payload": {"aps": {"alert":{"title":truncate(notification.title,65),"body":truncate(notification.message,100)},
                                     "badge":1,"sound":"default","mutable-content":1}}},
        "data": {k: str(v) for k,v in extra.items()},
    }

def build_apns_payload(notification, badge=1):
    from notifications.helpers import truncate, _get_sound
    return {"aps":{"alert":{"title":truncate(notification.title,65),"body":truncate(notification.message,100)},
                   "badge":badge,"sound":_get_sound(getattr(notification,"notification_type","")),"mutable-content":1,
                   "category":getattr(notification,"notification_type","").upper()},
            "notification_id":str(getattr(notification,"pk","")),"notification_type":getattr(notification,"notification_type",""),
            "action_url":getattr(notification,"action_url","") or ""}

def validate_web_push_subscription(subscription):
    if not subscription: return False, "Empty subscription"
    if "endpoint" not in subscription: return False, "Missing endpoint"
    if "keys" not in subscription: return False, "Missing keys"
    if "p256dh" not in subscription.get("keys",{}): return False, "Missing p256dh"
    if "auth" not in subscription.get("keys",{}): return False, "Missing auth"
    return True, ""

def get_badge_count(user):
    try:
        from notifications.models import Notification
        return Notification.objects.filter(user=user,is_read=False,is_deleted=False).count()
    except Exception: return 0

def reset_badge(user):
    try:
        from notifications.models import DeviceToken
        DeviceToken.objects.filter(user=user,is_active=True).update(badge_count=0)
    except Exception: pass

def get_push_eligible_users(user_ids):
    from notifications.selectors import device_get_fcm_tokens, device_get_apns_tokens
    return {"fcm": device_get_fcm_tokens(user_ids=user_ids), "apns": device_get_apns_tokens(user_ids=user_ids)}

def split_bd_international_phones(phones):
    from notifications.helpers import is_bdphone
    bd, intl = [], []
    for p in phones:
        (bd if is_bdphone(p) else intl).append(p)
    return bd, intl
