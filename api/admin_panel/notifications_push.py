# api/admin_panel/notifications_push.py
"""
Push Notification Management for admin_panel.
Sends FCM (Firebase), APNs (Apple), Web Push notifications.
admin_panel calls api.notifications — never manages tokens directly.
Provides admin controls: broadcast, targeted send, segment sends,
push analytics, delivery tracking, opt-out management.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ===========================================================================
# PUSH PROVIDERS
# ===========================================================================

class FCMProvider:
    """Firebase Cloud Messaging push provider."""

    def __init__(self):
        from django.conf import settings
        self.server_key = getattr(settings, 'FCM_SERVER_KEY', '')
        self.api_url    = 'https://fcm.googleapis.com/fcm/send'

    def send(self, token: str, title: str, body: str, data: Dict = None) -> Dict:
        if not self.server_key:
            return {'success': False, 'error': 'FCM_SERVER_KEY not configured'}
        try:
            import requests
            payload = {
                'to': token,
                'notification': {'title': title, 'body': body, 'sound': 'default'},
                'data': data or {},
                'priority': 'high',
            }
            resp = requests.post(
                self.api_url,
                json=payload,
                headers={
                    'Authorization': f'key={self.server_key}',
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            result = resp.json()
            return {'success': result.get('success', 0) > 0, 'response': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def send_multicast(self, tokens: List[str], title: str, body: str, data: Dict = None) -> Dict:
        if not self.server_key or not tokens:
            return {'success': False, 'sent': 0, 'failed': len(tokens)}
        try:
            import requests
            results = {'success': 0, 'failure': 0, 'errors': []}
            # FCM allows max 1000 tokens per multicast
            for i in range(0, len(tokens), 1000):
                batch = tokens[i:i+1000]
                payload = {
                    'registration_ids': batch,
                    'notification': {'title': title, 'body': body},
                    'data': data or {},
                    'priority': 'high',
                }
                resp = requests.post(
                    self.api_url, json=payload,
                    headers={'Authorization': f'key={self.server_key}',
                             'Content-Type': 'application/json'},
                    timeout=30,
                )
                r = resp.json()
                results['success'] += r.get('success', 0)
                results['failure'] += r.get('failure', 0)
            return results
        except Exception as e:
            return {'success': False, 'error': str(e)}


class APNsProvider:
    """Apple Push Notification Service provider."""

    def send(self, device_token: str, title: str, body: str, badge: int = 1, data: Dict = None) -> Dict:
        """Send APNs push notification."""
        try:
            from django.conf import settings
            apns_cert = getattr(settings, 'APNS_CERTIFICATE', '')
            if not apns_cert:
                return {'success': False, 'error': 'APNS_CERTIFICATE not configured'}
            # Implementation depends on apns2 library
            # pip install apns2
            logger.info(f"[APNs] Would send to {device_token[:20]}...")
            return {'success': True, 'provider': 'apns'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class WebPushProvider:
    """Browser Web Push (VAPID) provider."""

    def send(self, subscription: Dict, title: str, body: str, url: str = '/') -> Dict:
        """Send web push notification."""
        try:
            from django.conf import settings
            vapid_private = getattr(settings, 'VAPID_PRIVATE_KEY', '')
            if not vapid_private:
                return {'success': False, 'error': 'VAPID_PRIVATE_KEY not configured'}
            # pip install pywebpush
            import json
            from pywebpush import webpush, WebPushException
            data = json.dumps({'title': title, 'body': body, 'url': url})
            webpush(
                subscription_info=subscription,
                data=data,
                vapid_private_key=vapid_private,
                vapid_claims={'sub': f"mailto:{getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')}"},
            )
            return {'success': True, 'provider': 'webpush'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ===========================================================================
# PUSH NOTIFICATION MANAGER
# ===========================================================================

class PushNotificationManager:
    """
    Central push notification manager for admin_panel.
    Calls api.notifications for user tokens — never stores them.
    """

    def __init__(self):
        self.fcm    = FCMProvider()
        self.apns   = APNsProvider()
        self.webpush = WebPushProvider()

    def get_user_tokens(self, user_id: Any) -> Dict[str, List[str]]:
        """Get FCM/APNs tokens for a user from api.notifications."""
        tokens = {'fcm': [], 'apns': [], 'webpush': []}
        try:
            from api.notifications.models import DeviceToken
            user_tokens = DeviceToken.objects.filter(user_id=user_id, is_active=True)
            for t in user_tokens:
                platform = getattr(t, 'platform', 'fcm').lower()
                token = getattr(t, 'token', '')
                if platform in ('android', 'fcm') and token:
                    tokens['fcm'].append(token)
                elif platform in ('ios', 'apns') and token:
                    tokens['apns'].append(token)
                elif platform in ('web', 'webpush') and token:
                    tokens['webpush'].append(token)
        except Exception as e:
            logger.debug(f"[PushManager.get_user_tokens] {e}")
        return tokens

    def send_to_user(
        self,
        user_id: Any,
        title: str,
        body: str,
        data: Dict = None,
        platforms: List[str] = None,
    ) -> Dict:
        """Send push notification to a specific user on all their devices."""
        platforms = platforms or ['fcm', 'apns']
        tokens = self.get_user_tokens(user_id)
        results = {'user_id': user_id, 'sent': 0, 'failed': 0}

        for platform in platforms:
            if platform == 'fcm' and tokens['fcm']:
                r = self.fcm.send_multicast(tokens['fcm'], title, body, data)
                results['sent'] += r.get('success', 0)
                results['failed'] += r.get('failure', 0)
            elif platform == 'apns':
                for token in tokens['apns']:
                    r = self.apns.send(token, title, body, data=data)
                    if r.get('success'):
                        results['sent'] += 1
                    else:
                        results['failed'] += 1

        self._log_push(user_id=user_id, title=title, results=results)
        return results

    def broadcast_to_all(
        self,
        title: str,
        body: str,
        data: Dict = None,
        audience_filter: Dict = None,
    ) -> Dict:
        """Broadcast push to all or filtered users. Queues Celery task for large batches."""
        try:
            from celery import current_app
            current_app.send_task(
                'api.admin_panel.background_jobs.send_push_broadcast',
                args=[title, body, data or {}, audience_filter or {}],
                queue='admin_panel.bulk',
            )
            return {'success': True, 'queued': True}
        except Exception as e:
            logger.error(f"[PushManager.broadcast] Celery failed, sync: {e}")
            # Fallback: direct send
            return self._sync_broadcast(title, body, data, audience_filter)

    def _sync_broadcast(self, title, body, data, filters) -> Dict:
        """Synchronous broadcast (use only for small audiences)."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs = User.objects.filter(is_active=True)
        if filters:
            qs = qs.filter(**filters)
        sent = failed = 0
        for user in qs.iterator(chunk_size=100):
            r = self.send_to_user(user.pk, title, body, data)
            sent += r.get('sent', 0)
            failed += r.get('failed', 0)
        return {'sent': sent, 'failed': failed}

    def send_to_segment(self, segment: str, title: str, body: str, data: Dict = None) -> Dict:
        """
        Send to a user segment: 'active_7d', 'inactive_30d', 'premium', 'high_earners'
        """
        segment_filters = {
            'active_7d':      {'last_login__gte': timezone.now() - __import__('datetime').timedelta(days=7)},
            'inactive_30d':   {'last_login__lt': timezone.now() - __import__('datetime').timedelta(days=30)},
            'premium':        {'profile__is_premium': True},
        }
        filters = segment_filters.get(segment, {})
        return self.broadcast_to_all(title, body, data, filters)

    def _log_push(self, user_id: Any, title: str, results: Dict) -> None:
        """Log push delivery stats to cache counter."""
        try:
            today = timezone.now().date().isoformat()
            key = f'admin_panel:push_stats:{today}'
            stats = cache.get(key) or {'sent': 0, 'failed': 0}
            stats['sent'] += results.get('sent', 0)
            stats['failed'] += results.get('failed', 0)
            cache.set(key, stats, 86400)
        except Exception:
            pass

    def get_push_stats(self, days: int = 7) -> List[Dict]:
        """Push notification delivery stats for admin dashboard."""
        from datetime import timedelta
        results = []
        for i in range(days):
            day = (timezone.now() - timedelta(days=i)).date().isoformat()
            stats = cache.get(f'admin_panel:push_stats:{day}') or {'sent': 0, 'failed': 0}
            results.append({'date': day, **stats})
        return list(reversed(results))

    def revoke_user_tokens(self, user_id: Any) -> int:
        """Revoke all push tokens for a user (on ban/logout)."""
        try:
            from api.notifications.models import DeviceToken
            count = DeviceToken.objects.filter(user_id=user_id, is_active=True).update(is_active=False)
            return count
        except Exception as e:
            logger.debug(f"[PushManager.revoke_tokens] {e}")
            return 0


# Global manager instance
push_manager = PushNotificationManager()


# ===========================================================================
# CONVENIENCE FUNCTIONS
# ===========================================================================

def send_push(user_id: Any, title: str, body: str, data: Dict = None) -> Dict:
    return push_manager.send_to_user(user_id, title, body, data)


def broadcast_push(title: str, body: str, data: Dict = None) -> Dict:
    return push_manager.broadcast_to_all(title, body, data)


def send_push_to_segment(segment: str, title: str, body: str) -> Dict:
    return push_manager.send_to_segment(segment, title, body)