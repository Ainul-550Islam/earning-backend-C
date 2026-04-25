# earning_backend/api/notifications/services/NotificationDispatcher.py
"""
NotificationDispatcher — Central routing service.

Inspects a Notification's channel and dispatches it to the correct provider:
  in_app    → marks delivered (DB only, no external send)
  push      → FCMProvider (Android/Web) or APNsProvider (iOS)
  email     → SendGridProvider → SMTP fallback
  sms       → TwilioProvider or ShohoSMSProvider (for BD numbers)
  browser   → WebPushProvider
  telegram  → Telegram Bot (existing logic in NotificationService)
  whatsapp  → TwilioProvider.send_whatsapp
  all       → dispatches to all enabled channels

Also creates delivery log records (PushDeliveryLog, EmailDeliveryLog,
SMSDeliveryLog) via the channel models.
"""

import logging
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Routes a Notification object to the appropriate provider(s) and
    records delivery results in the channel log models.
    """

    # BD phone prefix — route to ShohoSMS for cost efficiency
    BD_PHONE_PREFIXES = ('01', '+8801', '8801', '0088')

    def __init__(self):
        # Lazy import providers to avoid circular imports at module load
        self._providers_loaded = False
        self._fcm = None
        self._apns = None
        self._sendgrid = None
        self._twilio = None
        self._shoho = None
        self._webpush = None

    # ------------------------------------------------------------------
    # Provider loading (lazy)
    # ------------------------------------------------------------------

    def _load_providers(self):
        if self._providers_loaded:
            return
        try:
            from .providers.FCMProvider import fcm_provider
            from .providers.APNsProvider import apns_provider
            from .providers.SendGridProvider import sendgrid_provider
            from .providers.TwilioProvider import twilio_provider
            from .providers.ShohoSMSProvider import shoho_sms_provider
            from .providers.WebPushProvider import web_push_provider

            self._fcm = fcm_provider
            self._apns = apns_provider
            self._sendgrid = sendgrid_provider
            self._twilio = twilio_provider
            self._shoho = shoho_sms_provider
            self._webpush = web_push_provider
            self._providers_loaded = True
        except Exception as exc:
            logger.error(f'NotificationDispatcher: failed to load providers — {exc}')

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(self, notification) -> Dict:
        """
        Dispatch a Notification to the correct provider(s) based on its channel.

        Args:
            notification: Core Notification model instance.

        Returns:
            Dict with: success (bool), channel, results (list of per-channel dicts),
            error (str).
        """
        self._load_providers()
        channel = getattr(notification, 'channel', 'in_app')

        dispatch_map = {
            'voice':     self._dispatch_voice,
            'teams':     self._dispatch_teams,
            'line':      self._dispatch_line,
            'in_app':    self._dispatch_in_app,
            'slack':     self._dispatch_slack,
            'discord':   self._dispatch_discord,
            'push':      self._dispatch_push,
            'email':     self._dispatch_email,
            'sms':       self._dispatch_sms,
            'browser':   self._dispatch_browser,
            'telegram':  self._dispatch_telegram,
            'whatsapp':  self._dispatch_whatsapp,
            'all':       self._dispatch_all,
        }

        handler = dispatch_map.get(channel, self._dispatch_unknown)

        try:
            result = handler(notification)
            result['channel'] = channel
            return result
        except Exception as exc:
            logger.error(
                f'NotificationDispatcher.dispatch exception for notification '
                f'#{notification.id} channel={channel}: {exc}'
            )
            return {
                'success': False,
                'channel': channel,
                'results': [],
                'error': str(exc),
            }

    # ------------------------------------------------------------------
    # Channel handlers
    # ------------------------------------------------------------------

    def _dispatch_in_app(self, notification) -> Dict:
        """
        In-app: mark notification as delivered (it's already in DB).
        Optionally create/update an InAppMessage record.
        """
        try:
            notification.mark_as_delivered()

            # Create InAppMessage for the frontend to pick up
            self._create_in_app_message(notification)

            return {
                'success': True,
                'results': [{'channel': 'in_app', 'success': True, 'provider': 'in_app'}],
                'error': '',
            }
        except Exception as exc:
            logger.error(f'_dispatch_in_app failed: {exc}')
            return {'success': False, 'results': [], 'error': str(exc)}

    def _dispatch_push(self, notification) -> Dict:
        """
        Push: send to all active push devices for the user.
        Chooses FCM (Android/Web) or APNs (iOS) per device.
        """
        from notifications.models import DeviceToken

        results = []
        any_success = False

        devices = DeviceToken.objects.filter(
            user=notification.user,
            is_active=True,
            push_enabled=True,
        ).select_related()

        if not devices.exists():
            return {
                'success': False,
                'results': [],
                'error': 'No active push devices found for user',
            }

        for device in devices:
            result = self._send_to_device(notification, device)
            results.append(result)
            if result.get('success'):
                any_success = True

        return {
            'success': any_success,
            'results': results,
            'error': '' if any_success else 'All device sends failed',
        }

    def _dispatch_email(self, notification) -> Dict:
        """Email: SendGrid → SMTP fallback."""
        user = notification.user
        to_email = getattr(user, 'email', '') or ''

        if not to_email:
            return {
                'success': False,
                'results': [],
                'error': 'User has no email address',
            }

        # Build content via existing NotificationService helper if available
        html_content = self._build_email_html(notification)
        text_content = getattr(notification, 'message', '')
        subject = getattr(notification, 'title', 'Notification')
        notif_id = str(notification.id)

        # Try SendGrid first
        result = None
        if self._sendgrid and self._sendgrid.is_available():
            result = self._sendgrid.send(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                notification_id=notif_id,
            )

        # Fallback to SMTP
        if not result or not result.get('success'):
            result = self._send_via_smtp(to_email, subject, html_content, text_content)

        # Record delivery log
        self._create_email_log(notification, to_email, result)

        if result.get('success'):
            notification.mark_as_sent()

        return {
            'success': result.get('success', False),
            'results': [result],
            'error': result.get('error', ''),
        }

    def _dispatch_sms(self, notification) -> Dict:
        """SMS: ShohoSMS for BD numbers, Twilio for international."""
        user = notification.user
        phone = getattr(user, 'phone_number', '') or getattr(user, 'phone', '') or ''

        if not phone:
            return {
                'success': False,
                'results': [],
                'error': 'User has no phone number',
            }

        message_body = f"{notification.title}: {notification.message}"

        # Route to ShohoSMS for Bangladesh numbers
        if self._is_bd_number(phone) and self._shoho and self._shoho.is_available():
            result = self._shoho.send_sms(
                to_phone=phone,
                body=message_body,
                notification_id=str(notification.id),
            )
        elif self._twilio and self._twilio.is_available():
            result = self._twilio.send_sms(
                to_phone=phone,
                body=message_body,
                notification_id=str(notification.id),
            )
        else:
            return {
                'success': False,
                'results': [],
                'error': 'No SMS provider available',
            }

        # Record delivery log
        self._create_sms_log(notification, phone, result)

        if result.get('success'):
            notification.mark_as_sent()

        return {
            'success': result.get('success', False),
            'results': [result],
            'error': result.get('error', ''),
        }

    def _dispatch_browser(self, notification) -> Dict:
        """Browser push via WebPushProvider."""
        from notifications.models import DeviceToken

        devices = DeviceToken.objects.filter(
            user=notification.user,
            is_active=True,
            platform='progressive_web_app',
        )

        if not devices.exists():
            return {
                'success': False,
                'results': [],
                'error': 'No browser push subscriptions found for user',
            }

        results = []
        any_success = False

        for device in devices:
            sub = device.web_push_token if hasattr(device, 'web_push_token') else {}
            if not sub:
                continue

            if self._webpush and self._webpush.is_available():
                result = self._webpush.send(
                    subscription_info=sub,
                    notification=notification,
                )
            else:
                result = {
                    'success': False,
                    'provider': 'web_push',
                    'error': 'WebPushProvider not available',
                }

            results.append(result)
            if result.get('success'):
                any_success = True
            elif result.get('is_invalid_subscription'):
                device.deactivate()

        return {
            'success': any_success,
            'results': results,
            'error': '' if any_success else 'All web push sends failed',
        }

    def _dispatch_telegram(self, notification) -> Dict:
        """Telegram: delegate to existing NotificationService._send_telegram logic."""
        try:
            from notifications.services import notification_service
            result = notification_service._send_telegram(notification)
            return {
                'success': result.get('success', False),
                'results': [result],
                'error': result.get('error', ''),
            }
        except Exception as exc:
            return {'success': False, 'results': [], 'error': str(exc)}

    def _dispatch_whatsapp(self, notification) -> Dict:
        """WhatsApp via TwilioProvider."""
        user = notification.user
        phone = getattr(user, 'phone_number', '') or getattr(user, 'phone', '') or ''

        if not phone:
            return {
                'success': False,
                'results': [],
                'error': 'User has no phone number for WhatsApp',
            }

        if not (self._twilio and self._twilio.is_available()):
            return {
                'success': False,
                'results': [],
                'error': 'TwilioProvider not available for WhatsApp',
            }

        message_body = f"{notification.title}\n{notification.message}"
        result = self._twilio.send_whatsapp(
            to_phone=phone,
            body=message_body,
            notification_id=str(notification.id),
        )

        if result.get('success'):
            notification.mark_as_sent()

        return {
            'success': result.get('success', False),
            'results': [result],
            'error': result.get('error', ''),
        }

    def _dispatch_all(self, notification) -> Dict:
        """Send via all enabled channels."""
        channels = ['in_app', 'push', 'email', 'sms', 'browser']
        all_results = []
        any_success = False

        for channel in channels:
            # Temporarily override channel for sub-dispatch
            original_channel = notification.channel
            notification.channel = channel
            try:
                result = self.dispatch(notification)
                all_results.extend(result.get('results', []))
                if result.get('success'):
                    any_success = True
            except Exception as exc:
                logger.warning(f'_dispatch_all: channel {channel} failed — {exc}')
            finally:
                notification.channel = original_channel

        return {
            'success': any_success,
            'results': all_results,
            'error': '' if any_success else 'All channels failed',
        }

    def _dispatch_slack(self, notification) -> Dict:
        """Slack: admin alerts and community notifications."""
        try:
            if self._providers_loaded:
                from .providers.SlackProvider import slack_provider
                if slack_provider.is_available():
                    result = slack_provider.send(notification)
                    if result.get('success'):
                        notification.mark_as_sent()
                    return {'success': result.get('success', False), 'results': [result], 'error': result.get('error', '')}
            return {'success': False, 'results': [], 'error': 'SlackProvider not available'}
        except Exception as exc:
            return {'success': False, 'results': [], 'error': str(exc)}

    def _dispatch_discord(self, notification) -> Dict:
        """Discord: community announcements and achievement notifications."""
        try:
            if self._providers_loaded:
                from .providers.DiscordProvider import discord_provider
                if discord_provider.is_available():
                    result = discord_provider.send(notification)
                    if result.get('success'):
                        notification.mark_as_sent()
                    return {'success': result.get('success', False), 'results': [result], 'error': result.get('error', '')}
            return {'success': False, 'results': [], 'error': 'DiscordProvider not available'}
        except Exception as exc:
            return {'success': False, 'results': [], 'error': str(exc)}

    def _dispatch_unknown(self, notification) -> Dict:
        channel = getattr(notification, 'channel', 'unknown')
        logger.warning(f'NotificationDispatcher: unknown channel "{channel}"')
        return {
            'success': False,
            'results': [],
            'error': f'Unknown notification channel: {channel}',
        }

    # ------------------------------------------------------------------
    # Device-level push routing
    # ------------------------------------------------------------------

    def _send_to_device(self, notification, device) -> Dict:
        """Route a push to FCM or APNs depending on device type."""
        device_type = getattr(device, 'device_type', '')
        platform = getattr(device, 'platform', '')

        result: Dict = {}

        if device_type == 'ios' and self._apns and self._apns.is_available():
            apns_token = getattr(device, 'apns_token', '') or ''
            if apns_token:
                result = self._apns.send(device_token=apns_token, notification=notification)
            else:
                result = {'success': False, 'error': 'No APNs token on device', 'provider': 'apns'}

        elif self._fcm and self._fcm.is_available():
            fcm_token = getattr(device, 'fcm_token', '') or device.get_push_token()
            if fcm_token and isinstance(fcm_token, str):
                result = self._fcm.send(token=fcm_token, notification=notification)
            elif isinstance(fcm_token, dict):
                # Web push subscription stored on DeviceToken
                if self._webpush and self._webpush.is_available():
                    result = self._webpush.send(
                        subscription_info=fcm_token,
                        notification=notification,
                    )
                else:
                    result = {'success': False, 'error': 'No WebPushProvider for web subscription', 'provider': 'web_push'}
            else:
                result = {'success': False, 'error': 'No FCM token on device', 'provider': 'fcm'}
        else:
            result = {'success': False, 'error': 'No push provider available', 'provider': 'none'}

        # Update device stats
        if result.get('success'):
            try:
                device.increment_push_delivered()
            except Exception:
                pass
        else:
            try:
                device.increment_push_failed()
            except Exception:
                pass
            # Deactivate on permanent token failure
            if result.get('is_invalid_token') or result.get('is_invalid_subscription'):
                try:
                    device.deactivate()
                except Exception:
                    pass

        # Create PushDeliveryLog
        self._create_push_log(notification, device, result)

        return result

    # ------------------------------------------------------------------
    # Delivery log creation helpers
    # ------------------------------------------------------------------

    def _create_push_log(self, notification, device, result: Dict):
        try:
            from notifications.models.channel import PushDeliveryLog
            log = PushDeliveryLog.objects.create(
                device=device,
                notification=notification,
                status='delivered' if result.get('success') else 'failed',
                provider=result.get('provider', ''),
                provider_message_id=result.get('message_id', ''),
                error_message=result.get('error', ''),
                delivered_at=timezone.now() if result.get('success') else None,
            )
        except Exception as exc:
            logger.warning(f'Failed to create PushDeliveryLog: {exc}')

    def _create_email_log(self, notification, recipient: str, result: Dict):
        try:
            from notifications.models.channel import EmailDeliveryLog
            EmailDeliveryLog.objects.create(
                notification=notification,
                recipient=recipient,
                provider=result.get('provider', ''),
                message_id=result.get('message_id', ''),
                status='sent' if result.get('success') else 'failed',
                error_message=result.get('error', ''),
            )
        except Exception as exc:
            logger.warning(f'Failed to create EmailDeliveryLog: {exc}')

    def _create_sms_log(self, notification, phone: str, result: Dict):
        try:
            from notifications.models.channel import SMSDeliveryLog
            SMSDeliveryLog.objects.create(
                notification=notification,
                phone=phone,
                gateway=result.get('provider', 'twilio'),
                provider_sid=result.get('sid', ''),
                status='sent' if result.get('success') else 'failed',
                error_message=result.get('error', ''),
            )
        except Exception as exc:
            logger.warning(f'Failed to create SMSDeliveryLog: {exc}')

    def _create_in_app_message(self, notification):
        """Create an InAppMessage record from the notification."""
        try:
            from notifications.models.channel import InAppMessage
            InAppMessage.objects.create(
                user=notification.user,
                notification=notification,
                message_type='toast',
                title=notification.title,
                body=notification.message,
                icon_url=getattr(notification, 'icon_url', '') or '',
                cta_url=getattr(notification, 'action_url', '') or '',
                cta_text=getattr(notification, 'action_text', '') or '',
                display_priority=self._priority_to_int(getattr(notification, 'priority', 'medium')),
            )
        except Exception as exc:
            logger.warning(f'Failed to create InAppMessage: {exc}')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_bd_number(self, phone: str) -> bool:
        """Return True if the phone number is Bangladeshi."""
        clean = phone.strip().replace(' ', '').replace('-', '')
        for prefix in self.BD_PHONE_PREFIXES:
            if clean.startswith(prefix):
                return True
        return False

    def _build_email_html(self, notification) -> str:
        """Build HTML email content. Delegates to existing service if available."""
        try:
            from notifications.services import notification_service
            return notification_service._build_email_content(notification)
        except Exception:
            return f'<h2>{notification.title}</h2><p>{notification.message}</p>'

    def _send_via_smtp(self, to_email: str, subject: str, html: str, text: str) -> Dict:
        """Fallback SMTP send using Django's email backend."""
        import uuid
        try:
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings as dj_settings

            from_email = getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=from_email,
                to=[to_email],
            )
            msg.attach_alternative(html, 'text/html')
            msg.send()
            return {
                'success': True,
                'provider': 'smtp',
                'message_id': str(uuid.uuid4()),
                'error': '',
            }
        except Exception as exc:
            return {
                'success': False,
                'provider': 'smtp',
                'message_id': '',
                'error': str(exc),
            }

    @staticmethod
    def _priority_to_int(priority: str) -> int:
        mapping = {
            'critical': 10,
            'urgent': 9,
            'high': 7,
            'medium': 5,
            'low': 3,
            'lowest': 1,
        }
        return mapping.get(priority, 5)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
notification_dispatcher = NotificationDispatcher()
