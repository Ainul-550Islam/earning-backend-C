# api/support/webhooks.py
import json
import hmac
import hashlib
import logging
import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


class OutgoingWebhookSender:
    TIMEOUT = 10

    def send(self, url: str, event: str, payload: dict, secret: str = '') -> bool:
        try:
            body = json.dumps({'event': event, 'timestamp': timezone.now().isoformat(), 'data': payload})
            headers = {'Content-Type': 'application/json', 'X-Support-Event': event}
            if secret:
                sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
                headers['X-Support-Signature'] = f'sha256={sig}'
            response = requests.post(url, data=body, headers=headers, timeout=self.TIMEOUT)
            if response.ok:
                logger.info(f'Webhook: {event} to {url} [{response.status_code}]')
                return True
            return False
        except Exception as e:
            logger.error(f'Webhook error {event}: {e}')
            return False

    def send_ticket_event(self, ticket, event: str) -> None:
        try:
            from api.support.models import SupportSettings
            obj, _ = SupportSettings.objects.get_or_create(id=1)
            if obj.slack_webhook_url:
                payload = {
                    'text': f'*Support: {event}* | Ticket: {ticket.ticket_id} | User: {ticket.user.username} | Priority: {ticket.priority.upper()}'
                }
                self.send(obj.slack_webhook_url, event, payload)
        except Exception as e:
            logger.debug(f'send_ticket_event: {e}')


webhook_sender = OutgoingWebhookSender()