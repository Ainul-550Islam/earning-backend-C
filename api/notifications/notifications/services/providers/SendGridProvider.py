# earning_backend/api/notifications/services/providers/SendGridProvider.py
"""
SendGridProvider — Email delivery via SendGrid.

Handles:
  - Single transactional email send
  - Template-based sends (SendGrid Dynamic Templates)
  - Batch sends (up to 1000 recipients via personalizations)
  - Webhook event processing (delivered, opened, clicked, bounced, spam)

Settings required:
    SENDGRID_API_KEY         — SendGrid API key (starts with 'SG.')
    DEFAULT_FROM_EMAIL       — Sender address, e.g. "no-reply@yourapp.com"
    DEFAULT_FROM_NAME        — (optional) Sender display name
    SENDGRID_SANDBOX_MODE    — (optional bool, default False) test without sending

Dependencies:
    pip install sendgrid
"""

import logging
import uuid
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SendGridProvider class
# ---------------------------------------------------------------------------

class SendGridProvider:
    """
    Wrapper around the sendgrid Python SDK.
    Exposes send / send_template / send_bulk / process_webhook methods.
    """

    def __init__(self):
        self._api_key: str = getattr(settings, 'SENDGRID_API_KEY', '')
        self._from_email: str = getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'
        )
        self._from_name: str = getattr(settings, 'DEFAULT_FROM_NAME', '')
        self._sandbox: bool = getattr(settings, 'SENDGRID_SANDBOX_MODE', False)
        self._available: bool = bool(self._api_key)
        self._client = None

        if self._available:
            try:
                from sendgrid import SendGridAPIClient
                self._client = SendGridAPIClient(self._api_key)
                logger.info('SendGridProvider: client initialised.')
            except ImportError:
                logger.error(
                    'SendGridProvider: sendgrid package not installed — '
                    'pip install sendgrid'
                )
                self._available = False
            except Exception as exc:
                logger.error(f'SendGridProvider: init failed — {exc}')
                self._available = False
        else:
            logger.warning('SendGridProvider: SENDGRID_API_KEY not configured.')

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._available

    def send(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str = '',
        reply_to: str = '',
        custom_headers: Optional[Dict] = None,
        categories: Optional[List[str]] = None,
        notification_id: str = '',
    ) -> Dict:
        """
        Send a single transactional email.

        Returns:
            Dict with keys: success, provider, message_id, status_code, error.
        """
        if not self._available:
            return self._unavailable_response()

        try:
            from sendgrid.helpers.mail import (
                Mail, Content, To, From, ReplyTo,
                MailSettings, SandBoxMode, Category,
            )

            from_addr = (
                f'{self._from_name} <{self._from_email}>'
                if self._from_name
                else self._from_email
            )

            message = Mail(
                from_email=from_addr,
                to_emails=to_email,
                subject=subject,
                plain_text_content=text_content or None,
                html_content=html_content,
            )

            if reply_to:
                message.reply_to = ReplyTo(reply_to)

            if custom_headers:
                for k, v in custom_headers.items():
                    message.header = (k, str(v))

            if categories:
                for cat in categories:
                    message.category = Category(cat)

            # Tracking
            if notification_id:
                message.header = ('X-Notification-ID', notification_id)

            if self._sandbox:
                message.mail_settings = MailSettings()
                message.mail_settings.sandbox_mode = SandBoxMode(enable=True)

            response = self._client.send(message)
            msg_id = response.headers.get('X-Message-Id', str(uuid.uuid4()))

            return {
                'success': True,
                'provider': 'sendgrid',
                'message_id': msg_id,
                'status_code': response.status_code,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'SendGridProvider.send failed to {to_email}: {exc}')
            return {
                'success': False,
                'provider': 'sendgrid',
                'message_id': '',
                'status_code': 0,
                'error': str(exc),
            }

    def send_template(
        self,
        to_email: str,
        template_id: str,
        dynamic_data: Optional[Dict] = None,
        subject_override: str = '',
        reply_to: str = '',
        notification_id: str = '',
    ) -> Dict:
        """
        Send an email using a SendGrid Dynamic Template.

        Args:
            to_email:       Recipient email.
            template_id:    SendGrid Dynamic Template ID (e.g. 'd-xxxxxxxx').
            dynamic_data:   Template variables dict.
            subject_override: Override the template subject line.
            reply_to:       Optional reply-to address.
            notification_id: Traced notification ID for webhook matching.
        """
        if not self._available:
            return self._unavailable_response()

        try:
            from sendgrid.helpers.mail import Mail, DynamicTemplateData, To

            from_addr = (
                f'{self._from_name} <{self._from_email}>'
                if self._from_name
                else self._from_email
            )

            message = Mail(from_email=from_addr, to_emails=to_email)
            message.template_id = template_id

            if dynamic_data:
                message.dynamic_template_data = dynamic_data

            if subject_override:
                message.subject = subject_override

            if reply_to:
                from sendgrid.helpers.mail import ReplyTo
                message.reply_to = ReplyTo(reply_to)

            if notification_id:
                message.header = ('X-Notification-ID', notification_id)

            response = self._client.send(message)
            msg_id = response.headers.get('X-Message-Id', str(uuid.uuid4()))

            return {
                'success': True,
                'provider': 'sendgrid',
                'message_id': msg_id,
                'status_code': response.status_code,
                'error': '',
                'template_id': template_id,
            }

        except Exception as exc:
            logger.error(f'SendGridProvider.send_template failed to {to_email}: {exc}')
            return {
                'success': False,
                'provider': 'sendgrid',
                'message_id': '',
                'status_code': 0,
                'error': str(exc),
                'template_id': template_id,
            }

    def send_bulk(
        self,
        recipients: List[Dict],
        subject: str,
        html_content: str,
        text_content: str = '',
        categories: Optional[List[str]] = None,
    ) -> Dict:
        """
        Send to multiple recipients using SendGrid personalizations.
        Each recipient dict: {'email': str, 'name': str (opt),
                               'substitutions': dict (opt)}

        SendGrid allows up to 1000 personalizations per API call.

        Returns:
            Dict with success, total, success_count, failure_count,
            message_id, error.
        """
        if not self._available:
            return {
                'success': False,
                'provider': 'sendgrid',
                'error': 'SendGridProvider not available',
                'total': len(recipients),
                'success_count': 0,
                'failure_count': len(recipients),
                'message_id': '',
            }

        BATCH_SIZE = 1000
        total_success = 0
        total_failure = 0
        message_ids: List[str] = []

        try:
            from sendgrid.helpers.mail import (
                Mail, Personalization, To, Content, Category
            )

            for i in range(0, len(recipients), BATCH_SIZE):
                batch = recipients[i: i + BATCH_SIZE]

                from_addr = (
                    f'{self._from_name} <{self._from_email}>'
                    if self._from_name
                    else self._from_email
                )

                message = Mail(from_email=from_addr)
                message.subject = subject
                message.add_content(Content('text/html', html_content))
                if text_content:
                    message.add_content(Content('text/plain', text_content))

                if categories:
                    for cat in categories:
                        message.category = Category(cat)

                for recipient in batch:
                    p = Personalization()
                    p.add_to(To(
                        email=recipient['email'],
                        name=recipient.get('name', ''),
                    ))
                    subs = recipient.get('substitutions', {})
                    for k, v in subs.items():
                        p.add_substitution(k, str(v))
                    message.add_personalization(p)

                response = self._client.send(message)
                if 200 <= response.status_code < 300:
                    total_success += len(batch)
                    msg_id = response.headers.get('X-Message-Id', str(uuid.uuid4()))
                    message_ids.append(msg_id)
                else:
                    total_failure += len(batch)
                    logger.error(
                        f'SendGridProvider.send_bulk batch failed: '
                        f'status={response.status_code}'
                    )

        except Exception as exc:
            logger.error(f'SendGridProvider.send_bulk failed: {exc}')
            return {
                'success': False,
                'provider': 'sendgrid',
                'error': str(exc),
                'total': len(recipients),
                'success_count': total_success,
                'failure_count': len(recipients) - total_success,
                'message_id': ','.join(message_ids),
            }

        return {
            'success': total_success > 0,
            'provider': 'sendgrid',
            'error': '',
            'total': len(recipients),
            'success_count': total_success,
            'failure_count': total_failure,
            'message_id': ','.join(message_ids),
        }

    def process_webhook_event(self, event: Dict) -> Dict:
        """
        Process a single SendGrid inbound webhook event dict.

        Updates EmailDeliveryLog based on the event type.
        Returns a summary dict.

        Common event types:
            delivered, open, click, bounce, spamreport, unsubscribe,
            group_unsubscribe, deferred, dropped.
        """
        event_type = event.get('event', '').lower()
        message_id = event.get('sg_message_id', '').split('.')[0]  # strip suffix
        timestamp = event.get('timestamp')
        email = event.get('email', '')

        result = {
            'event_type': event_type,
            'message_id': message_id,
            'email': email,
            'processed': False,
            'error': '',
        }

        if not message_id:
            result['error'] = 'No sg_message_id in event'
            return result

        try:
            from api.notifications.models.channel import EmailDeliveryLog

            log = EmailDeliveryLog.objects.filter(message_id=message_id).first()
            if not log:
                result['error'] = f'No EmailDeliveryLog found for message_id {message_id}'
                return result

            if event_type == 'delivered':
                log.status = 'delivered'
                log.save(update_fields=['status', 'updated_at'])

            elif event_type == 'open':
                log.record_open()

            elif event_type == 'click':
                log.record_click()

            elif event_type in ('bounce', 'blocked'):
                log.mark_bounced(error_message=event.get('reason', ''))

            elif event_type == 'spamreport':
                log.status = 'spam'
                log.save(update_fields=['status', 'updated_at'])

            elif event_type in ('unsubscribe', 'group_unsubscribe'):
                log.status = 'unsubscribed'
                log.save(update_fields=['status', 'updated_at'])

            result['processed'] = True

        except Exception as exc:
            logger.error(f'SendGridProvider.process_webhook_event failed: {exc}')
            result['error'] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _unavailable_response(self) -> Dict:
        return {
            'success': False,
            'provider': 'sendgrid',
            'message_id': '',
            'status_code': 0,
            'error': 'SendGridProvider not available — SENDGRID_API_KEY not configured',
        }


    def send_gif_email(self, to_email: str, subject: str, message: str,
                        gif_url: str, alt_text: str = '', **kwargs) -> dict:
        """
        Send an email with an animated GIF in the body.
        Most email clients display GIF animation; Outlook shows first frame.
        """
        html_content = f"""
        <html><body>
        <p>{message}</p>
        <img src="{gif_url}" alt="{alt_text or subject}"
             style="max-width:600px;width:100%;border-radius:8px;" />
        <br><br>
        <small style="color:#999;">If the GIF is not visible, please view this email in a browser.</small>
        </body></html>
        """
        return self.send_html_email(to_email, subject, html_content, **kwargs)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
sendgrid_provider = SendGridProvider()
