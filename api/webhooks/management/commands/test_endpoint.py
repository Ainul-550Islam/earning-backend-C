"""Test Endpoint Management Command

This Django management command sends a test payload
to a specific webhook endpoint for validation and debugging.
"""

import json
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.module_loading import import_string

from ...services.core import DispatchService
from ...models import WebhookEndpoint, WebhookDeliveryLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to test webhook endpoints.
    Sends test payloads to validate endpoint configuration.
    """
    
    help = 'Send test payload to a specific webhook endpoint'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'endpoint_id',
            type=str,
            help='ID of the webhook endpoint to test',
        )
        parser.add_argument(
            '--event-type',
            type=str,
            default='test.event',
            help='Event type for test payload',
        )
        parser.add_argument(
            '--payload',
            type=str,
            default='{"test": "data"}',
            help='JSON payload to send (default: test event)',
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Send asynchronously (queue for background processing)',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        endpoint_id = options['endpoint_id']
        event_type = options['event_type']
        payload = options['payload']
        async_send = options['async']
        
        try:
            # Get endpoint
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
            
            self.stdout.write(
                f"Testing endpoint: {endpoint.target_url} ({endpoint.get_status_display()})"
            )
            
            # Parse payload
            try:
                test_payload = json.loads(payload)
            except json.JSONDecodeError:
                self.stderr.write(
                    self.style.ERROR("Invalid JSON payload provided")
                )
                return
            
            # BUG FIX: this used to pre-create a WebhookDeliveryLog and pass
            # it as delivery_log=... to DispatchService.emit()/emit_async().
            # Neither call was valid: emit() has no delivery_log parameter
            # (confirmed against its real signature - it creates its own
            # delivery log internally via _emit_sync()/_emit_async(), with
            # no way to inject an existing one), and emit_async() doesn't
            # exist on DispatchService at all - there's only emit(...,
            # async_emit=True). Both branches raised (TypeError and
            # AttributeError respectively), caught by the broad except
            # below, so this command failed 100% of the time in both modes
            # regardless of a real endpoint/payload. The pre-created log
            # was also silently orphaned even before that - never touched
            # by whatever emit() actually did.
            dispatch_service = DispatchService()
            success = dispatch_service.emit(
                endpoint=endpoint,
                event_type=event_type,
                payload=test_payload,
                async_emit=async_send,
            )

            if success:
                verb = "queued" if async_send else "sent"
                self.stdout.write(
                    self.style.SUCCESS(f"Test webhook {verb} successfully")
                )
                # emit() doesn't hand back the delivery log it created
                # internally, but for a synchronous send it has already
                # completed by the time we get here, so the most recent
                # matching log for this endpoint/event is genuinely it -
                # shown as a convenience, not required for correctness.
                if not async_send:
                    latest_log = WebhookDeliveryLog.objects.filter(
                        endpoint=endpoint, event_type=event_type,
                    ).order_by('-created_at').first()
                    if latest_log:
                        self.stdout.write(f"  Delivery log ID: {latest_log.id}")
            else:
                verb = "queue" if async_send else "send"
                self.stderr.write(
                    self.style.ERROR(f"Failed to {verb} test webhook")
                )
            
        except WebhookEndpoint.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"Webhook endpoint with ID {endpoint_id} not found")
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Test failed: {e}")
            )
            logger.error(f"Webhook test failed: {e}")
    
    def _get_test_payloads(self) -> dict:
        """Get predefined test payloads for common event types."""
        return {
            'user.created': {
                'user_id': 12345,
                'email': 'test@example.com',
                'created_at': '2024-01-01T00:00:00Z',
            },
            'wallet.transaction.created': {
                'transaction_id': 'txn_12345',
                'user_id': 12345,
                'amount': 100.00,
                'currency': 'USD',
                'type': 'credit',
            },
            'offer.credited': {
                'offer_id': 'offer_12345',
                'user_id': 12345,
                'amount': 5.00,
                'currency': 'USD',
                'campaign_id': 'campaign_12345',
            },
            'payment.succeeded': {
                'payment_id': 'payment_12345',
                'user_id': 12345,
                'amount': 50.00,
                'currency': 'USD',
                'method': 'credit_card',
            },
            'fraud.detected': {
                'user_id': 12345,
                'transaction_id': 'txn_12345',
                'fraud_type': 'suspicious_activity',
                'risk_score': 85,
                'detected_at': '2024-01-01T00:00:00Z',
            },
            'system.maintenance': {
                'message': 'Scheduled maintenance',
                'start_time': '2024-01-01T02:00:00Z',
                'duration_minutes': 30,
                'affected_services': ['webhooks', 'api'],
            },
        }