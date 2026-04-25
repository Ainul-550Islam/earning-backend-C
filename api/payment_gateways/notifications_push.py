# api/payment_gateways/notifications_push.py
# Push notification system for payment events
# Supports: Firebase FCM (mobile), Web Push, Channels (WebSocket), APNs
# "Do not summarize or skip any logic. Provide the full code."

import logging
from decimal import Decimal
from typing import List, Optional, Dict
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class PushNotificationService:
    """
    Multi-channel push notification service for payment events.

    Channels:
        1. Firebase FCM — Android/iOS mobile push
        2. Web Push (VAPID) — Browser notifications
        3. Django Channels — Real-time WebSocket
        4. Your existing api.notifications — In-app notifications

    All channels are optional — falls back gracefully if not configured.

    Settings required:
        FIREBASE_SERVER_KEY or GOOGLE_APPLICATION_CREDENTIALS
        VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS_EMAIL

    Usage:
        push = PushNotificationService()
        push.send_deposit_completed(user, Decimal('500'), 'bkash', 'REF-001')
    """

    # ── Notification templates ──────────────────────────────────────────────────
    TEMPLATES = {
        'deposit_completed': {
            'title': '✅ Deposit Confirmed',
            'body':  'Your {currency} {amount} deposit via {gateway} is confirmed!',
            'icon':  '/static/icons/deposit.png',
            'data':  {'action': 'view_transactions'},
        },
        'deposit_failed': {
            'title': '❌ Deposit Failed',
            'body':  'Your {currency} {amount} deposit via {gateway} failed. Tap to retry.',
            'icon':  '/static/icons/error.png',
            'data':  {'action': 'retry_deposit'},
        },
        'withdrawal_processed': {
            'title': '💸 Withdrawal Processed',
            'body':  'Your {currency} {amount} withdrawal has been processed!',
            'icon':  '/static/icons/withdrawal.png',
            'data':  {'action': 'view_transactions'},
        },
        'withdrawal_approved': {
            'title': '👍 Withdrawal Approved',
            'body':  'Your {currency} {amount} withdrawal is approved and processing.',
            'icon':  '/static/icons/check.png',
            'data':  {'action': 'view_transactions'},
        },
        'withdrawal_rejected': {
            'title': '❌ Withdrawal Rejected',
            'body':  'Your withdrawal was rejected. Tap for details.',
            'icon':  '/static/icons/error.png',
            'data':  {'action': 'view_payouts'},
        },
        'conversion_earned': {
            'title': '🎉 New Earning!',
            'body':  'You earned {currency} {payout} from {offer}!',
            'icon':  '/static/icons/money.png',
            'data':  {'action': 'view_earnings'},
        },
        'payout_scheduled': {
            'title': '📅 Payout Scheduled',
            'body':  'Your {currency} {amount} payout is scheduled for {date}.',
            'icon':  '/static/icons/calendar.png',
            'data':  {'action': 'view_payouts'},
        },
        'fraud_blocked': {
            'title': '🔒 Transaction Blocked',
            'body':  'A transaction was blocked for security. Contact support if this was you.',
            'icon':  '/static/icons/security.png',
            'data':  {'action': 'contact_support'},
        },
        'balance_low': {
            'title': '⚠️ Low Balance',
            'body':  'Your advertiser balance is below {threshold}. Top up to avoid paused campaigns.',
            'icon':  '/static/icons/warning.png',
            'data':  {'action': 'add_balance'},
        },
        'offer_capped': {
            'title': '⏸️ Offer Cap Reached',
            'body':  'Your offer "{offer}" has reached its daily cap and was paused.',
            'icon':  '/static/icons/pause.png',
            'data':  {'action': 'view_offers'},
        },
        'milestone_reached': {
            'title': '🏆 Milestone Reached!',
            'body':  'Congratulations! {message}',
            'icon':  '/static/icons/trophy.png',
            'data':  {'action': 'view_dashboard'},
        },
    }

    def send_deposit_completed(self, user, amount: Decimal,
                                gateway: str, reference_id: str = ''):
        """Send deposit confirmation notification."""
        self._send_to_user(user, 'deposit_completed', {
            'amount':    f'{float(amount):.2f}',
            'currency':  'BDT' if gateway in ('bkash','nagad','sslcommerz','amarpay','upay','shurjopay') else 'USD',
            'gateway':   gateway.upper(),
            'reference': reference_id,
        })

    def send_deposit_failed(self, user, amount: Decimal, gateway: str):
        """Send deposit failure notification."""
        self._send_to_user(user, 'deposit_failed', {
            'amount':  f'{float(amount):.2f}',
            'currency':'BDT' if gateway in ('bkash','nagad') else 'USD',
            'gateway': gateway.upper(),
        })

    def send_withdrawal_processed(self, user, amount: Decimal,
                                    method: str, reference_id: str = ''):
        """Send withdrawal processed notification."""
        self._send_to_user(user, 'withdrawal_processed', {
            'amount':  f'{float(amount):.2f}',
            'currency':'BDT' if method in ('bkash','nagad') else 'USD',
            'method':  method.upper(),
        })

    def send_withdrawal_approved(self, user, amount: Decimal, method: str):
        """Send withdrawal approval notification."""
        self._send_to_user(user, 'withdrawal_approved', {
            'amount':  f'{float(amount):.2f}',
            'currency':'USD',
            'method':  method.upper(),
        })

    def send_withdrawal_rejected(self, user, amount: Decimal, reason: str = ''):
        """Send withdrawal rejection notification."""
        self._send_to_user(user, 'withdrawal_rejected', {
            'amount': f'{float(amount):.2f}',
            'currency': 'USD',
            'reason': reason,
        })

    def send_conversion_earned(self, user, payout: Decimal,
                                offer_name: str, currency: str = 'USD'):
        """Send new conversion earning notification to publisher."""
        self._send_to_user(user, 'conversion_earned', {
            'payout':  f'{float(payout):.2f}',
            'currency': currency,
            'offer':    offer_name[:30],
        })

    def send_balance_low_alert(self, advertiser, current_balance: Decimal,
                                threshold: Decimal):
        """Alert advertiser when balance is low."""
        self._send_to_user(advertiser, 'balance_low', {
            'balance':   f'{float(current_balance):.2f}',
            'threshold': f'{float(threshold):.2f}',
        })

    def send_offer_capped(self, advertiser, offer_name: str):
        """Notify advertiser when offer cap is reached."""
        self._send_to_user(advertiser, 'offer_capped', {'offer': offer_name})

    def send_milestone_reached(self, user, message: str):
        """Send milestone achievement notification."""
        self._send_to_user(user, 'milestone_reached', {'message': message})

    def send_fraud_blocked(self, user):
        """Notify user of blocked fraud transaction."""
        self._send_to_user(user, 'fraud_blocked', {})

    def send_bulk(self, user_ids: List[int], template: str,
                   context: dict) -> dict:
        """Send push notification to multiple users."""
        sent = failed = 0
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for user in User.objects.filter(id__in=user_ids, is_active=True):
            try:
                self._send_to_user(user, template, context)
                sent += 1
            except Exception:
                failed += 1
        return {'sent': sent, 'failed': failed}

    def register_device_token(self, user, token: str,
                               platform: str = 'fcm') -> bool:
        """Register a device token for push notifications."""
        try:
            from api.payment_gateways.notifications.models import DeviceToken
            DeviceToken.objects.update_or_create(
                user=user, token=token,
                defaults={'platform': platform, 'is_active': True},
            )
            return True
        except Exception as e:
            logger.debug(f'Device token registration failed: {e}')
            return False

    def get_user_tokens(self, user) -> List[dict]:
        """Get all active device tokens for a user."""
        try:
            from api.payment_gateways.notifications.models import DeviceToken
            return list(
                DeviceToken.objects.filter(user=user, is_active=True)
                .values('token', 'platform')
            )
        except Exception:
            return []

    # ── Private methods ────────────────────────────────────────────────────────
    def _send_to_user(self, user, template_name: str, context: dict):
        """Send notification to all user's devices and channels."""
        template = self.TEMPLATES.get(template_name)
        if not template:
            logger.warning(f'Unknown notification template: {template_name}')
            return

        # Format message
        title = template['title']
        body  = template['body'].format(**context) if '{' in template['body'] else template['body']
        data  = {**template.get('data', {}), **context}

        # 1. WebSocket (real-time, always first)
        self._send_websocket(user, template_name, {'title': title, 'body': body, **data})

        # 2. Firebase FCM
        tokens = self.get_user_tokens(user)
        for token_info in tokens:
            if token_info['platform'] in ('fcm', 'android', 'ios'):
                self._send_fcm(token_info['token'], title, body, data)
            elif token_info['platform'] == 'web':
                self._send_web_push(token_info['token'], title, body, data)

        # 3. Your existing api.notifications (in-app)
        self._send_inapp(user, template_name, title, body, context)

        # 4. Try YOUR existing api.notifications app
        self._send_via_existing_app(user, template_name, context)

    def _send_fcm(self, token: str, title: str, body: str, data: dict):
        """Send via Firebase Cloud Messaging."""
        try:
            import requests
            server_key = getattr(settings, 'FIREBASE_SERVER_KEY', '')
            if not server_key:
                return
            payload = {
                'to': token,
                'notification': {'title': title, 'body': body, 'sound': 'default'},
                'data': {k: str(v) for k, v in data.items()},
                'priority': 'high',
            }
            resp = requests.post(
                'https://fcm.googleapis.com/fcm/send',
                json=payload,
                headers={'Authorization': f'key={server_key}', 'Content-Type': 'application/json'},
                timeout=5,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get('failure', 0) > 0:
                    logger.debug(f'FCM delivery failed: {result}')
        except Exception as e:
            logger.debug(f'FCM send failed: {e}')

    def _send_web_push(self, subscription_info: str, title: str, body: str, data: dict):
        """Send via Web Push Protocol (VAPID)."""
        try:
            import json as json_lib
            from pywebpush import webpush, WebPushException
            vapid_private = getattr(settings, 'VAPID_PRIVATE_KEY', '')
            vapid_email   = getattr(settings, 'VAPID_CLAIMS_EMAIL', 'mailto:admin@yourdomain.com')
            if not vapid_private:
                return
            subscription = json_lib.loads(subscription_info) if isinstance(subscription_info, str) else subscription_info
            webpush(
                subscription_info=subscription,
                data=json_lib.dumps({'title': title, 'body': body, 'data': data}),
                vapid_private_key=vapid_private,
                vapid_claims={'sub': vapid_email},
            )
        except ImportError:
            logger.debug('pywebpush not installed — web push disabled')
        except Exception as e:
            logger.debug(f'Web push failed: {e}')

    def _send_websocket(self, user, event_type: str, data: dict):
        """Send via Django Channels WebSocket."""
        try:
            from api.payment_gateways.routing import broadcast_payment_event
            broadcast_payment_event(user.id, f'notification_{event_type}', data)
        except Exception:
            pass

    def _send_inapp(self, user, template_name: str, title: str,
                     body: str, context: dict):
        """Create in-app notification record."""
        try:
            from api.payment_gateways.notifications.models import InAppNotification
            InAppNotification.objects.create(
                user=user, title=title, message=body,
                notification_type=template_name,
                metadata=context,
            )
        except Exception:
            pass

    def _send_via_existing_app(self, user, template_name: str, context: dict):
        """Try sending via your existing api.notifications app."""
        try:
            from api.notifications.services import NotificationService
            NotificationService().send(
                user=user, template=f'payment_{template_name}', context=context
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f'Existing notification app failed: {e}')


# Global push notification service
push_service = PushNotificationService()
