"""
SmartLink Business ViewSets
==============================
4 business-facing API viewsets:
  1. APIKeyViewSet         — publisher API key CRUD + rotate
  2. WebhookViewSet        — webhook endpoint CRUD + test delivery + delivery log
  3. PayoutViewSet         — payout records, batch management, gateway processing
  4. PublisherProfileViewSet — profile CRUD + GDPR consent + anonymize

Serializers are now imported from serializers/BillingSerializers.py.
(Previously they were defined inline here — moved for single-responsibility.)
"""
import logging
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication subclass that skips CSRF enforcement.
    Used exclusively on webhook endpoints that receive calls from
    external servers (PayPal, Wise) which never have a CSRF token.
    All security is handled via HMAC signature verification instead.
    """
    def enforce_csrf(self, request):
        return  # No CSRF check for webhook endpoints

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()
logger = logging.getLogger('smartlink.viewsets.business')

# ── Import from dedicated serializer file (no more inline definitions) ─────────
from api.smartlink.serializers.BillingSerializers import (
    APIKeyListSerializer,
    APIKeyCreateSerializer,
    APIKeyCreatedSerializer,
    WebhookEndpointSerializer,
    WebhookDeliveryLogSerializer,
    PublisherProfileSerializer,
    PublisherProfileAdminSerializer,
    PayoutRecordSerializer,
    PayoutRecordListSerializer,
    PayoutBatchSerializer,
    PayoutBatchCreateSerializer,
)
from api.smartlink.serializers.PublisherWalletSerializer import PublisherWalletSerializer


# ─────────────────────────────────────────────────────────────────────────────
# 1. APIKey ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class APIKeyViewSet(viewsets.ViewSet):
    """
    CRUD for publisher API keys.
    Uses PublisherAPIKeySerializer for create/update/list/retrieve.
    """
    def get_serializer_class(self):
        from api.smartlink.serializers.MissingTargetingSerializers import PublisherAPIKeySerializer
        return PublisherAPIKeySerializer

    """
    Manage publisher API keys.

    GET    /api/smartlink/publisher/api-keys/            — list keys
    POST   /api/smartlink/publisher/api-keys/            — create (returns raw key ONCE)
    DELETE /api/smartlink/publisher/api-keys/{id}/       — revoke
    POST   /api/smartlink/publisher/api-keys/{id}/rotate/ — generate new key, revoke old
    POST   /api/smartlink/publisher/api-keys/{id}/toggle/ — enable / disable
    """
    permission_classes = [IsAuthenticated]

    def _publisher_keys(self, user):
        from api.smartlink.models.billing import PublisherAPIKey
        return PublisherAPIKey.objects.filter(publisher=user).order_by('-created_at')

    def list(self, request):
        keys = self._publisher_keys(request.user)
        return Response(APIKeyListSerializer(keys, many=True).data)

    def create(self, request):
        ser = APIKeyCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        from api.smartlink.models.billing import PublisherAPIKey
        obj, raw_key = PublisherAPIKey.generate(
            publisher=request.user,
            name=d['name'],
            scope=d['scope'],
            allowed_ips=d.get('allowed_ips') or [],
            expires_at=d.get('expires_at'),
        )
        data = APIKeyListSerializer(obj).data
        data['raw_key'] = raw_key  # shown ONCE — not stored
        logger.info(f"API key created: {request.user.username} / {obj.name}")
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        from api.smartlink.models.billing import PublisherAPIKey
        from django.shortcuts import get_object_or_404
        key = get_object_or_404(PublisherAPIKey, pk=pk, publisher=request.user)
        key.delete()
        return Response({'message': 'API key revoked.'})

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Delete old key and issue a new one with the same config."""
        from api.smartlink.models.billing import PublisherAPIKey
        from django.shortcuts import get_object_or_404
        old = get_object_or_404(PublisherAPIKey, pk=pk, publisher=request.user)
        with transaction.atomic():
            obj, raw_key = PublisherAPIKey.generate(
                publisher=request.user,
                name=old.name,
                scope=old.scope,
                allowed_ips=old.allowed_ips,
                expires_at=old.expires_at,
            )
            old.delete()
        data = APIKeyListSerializer(obj).data
        data['raw_key'] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Enable or disable an API key without deleting it."""
        from api.smartlink.models.billing import PublisherAPIKey
        from django.shortcuts import get_object_or_404
        key = get_object_or_404(PublisherAPIKey, pk=pk, publisher=request.user)
        PublisherAPIKey.objects.filter(pk=key.pk).update(is_active=not key.is_active)
        key.refresh_from_db()
        return Response(APIKeyListSerializer(key).data)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Webhook ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class WebhookViewSet(viewsets.ModelViewSet):
    """
    Manage webhook endpoints and inspect delivery logs.

    GET    /api/smartlink/webhooks/                         — list endpoints
    POST   /api/smartlink/webhooks/                         — create endpoint
    PUT    /api/smartlink/webhooks/{id}/                    — update endpoint
    DELETE /api/smartlink/webhooks/{id}/                    — delete endpoint
    POST   /api/smartlink/webhooks/{id}/test/               — send test payload
    GET    /api/smartlink/webhooks/{id}/deliveries/         — delivery log
    POST   /api/smartlink/webhooks/{id}/retry-failed/       — retry dropped deliveries
    GET    /api/smartlink/webhooks/events/                  — list event names
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = WebhookEndpointSerializer

    def get_queryset(self):
        from api.smartlink.models.webhook import WebhookEndpoint
        if self.request.user.is_staff:
            return WebhookEndpoint.objects.all().select_related('publisher')
        return WebhookEndpoint.objects.filter(publisher=self.request.user)

    def perform_create(self, serializer):
        import secrets
        serializer.save(
            publisher=self.request.user,
            secret=secrets.token_hex(32),
        )

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Send a test ping payload to verify the endpoint is reachable."""
        endpoint = self.get_object()
        from api.smartlink.services.webhook.WebhookService import WebhookService
        from django.utils import timezone as tz
        svc = WebhookService()
        svc._deliver(endpoint, 'test', {
            'event':     'test',
            'message':   'SmartLink webhook test ping.',
            'timestamp': tz.now().isoformat(),
        })
        from api.smartlink.models.webhook import WebhookDeliveryLog
        last = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint, event='test'
        ).order_by('-created_at').first()
        if last:
            return Response({
                'status':     last.status,
                'http_status': last.http_status,
                'latency_ms': last.latency_ms,
                'error':      last.error_message or None,
            })
        return Response({'status': 'queued'})

    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """Return recent delivery log for this endpoint (last 100)."""
        endpoint = self.get_object()
        logs = endpoint.deliveries.order_by('-created_at')[:100]
        return Response(WebhookDeliveryLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'], url_path='retry-failed')
    def retry_failed(self, request, pk=None):
        """Re-queue all DROPPED deliveries for this endpoint."""
        endpoint = self.get_object()
        from api.smartlink.models.webhook import WebhookDeliveryLog
        from django.utils import timezone
        count = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint,
            status=WebhookDeliveryLog.Status.DROPPED,
        ).update(
            status=WebhookDeliveryLog.Status.RETRYING,
            next_retry_at=timezone.now(),
        )
        return Response({'requeued': count})

    @action(detail=False, methods=['get'])
    def events(self, request):
        """List all supported webhook event names."""
        from api.smartlink.models.webhook import WEBHOOK_EVENTS
        return Response([{'event': e, 'description': d} for e, d in WEBHOOK_EVENTS])


# ─────────────────────────────────────────────────────────────────────────────
# 3. Payout ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PayoutViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Publisher payout records and admin batch management.

    Publisher:
      GET /api/smartlink/payouts/            — own payout history
      GET /api/smartlink/payouts/{id}/       — payout detail
      GET /api/smartlink/payouts/wallet/     — wallet balance (PublisherWallet)
      GET /api/smartlink/payouts/summary/    — aggregate payout summary

    Admin:
      GET  /api/smartlink/payouts/batches/                            — all batches
      POST /api/smartlink/payouts/batches/                            — create batch
      POST /api/smartlink/payouts/batches/{id}/approve/               — approve all records
      POST /api/smartlink/payouts/batches/{id}/mark-paid/             — mark all paid
      POST /api/smartlink/payouts/calculate/                          — calculate for publisher
      POST /api/smartlink/payouts/{id}/process-payment/               — send to gateway
      POST /api/smartlink/payouts/batches/{id}/process-payments/      — send batch to gateways
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = PayoutRecordSerializer

    def get_queryset(self):
        from api.smartlink.models.billing import PayoutRecord
        if self.request.user.is_staff:
            return PayoutRecord.objects.all().select_related('publisher', 'batch')
        return PayoutRecord.objects.filter(publisher=self.request.user)

    # ── Publisher: wallet ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def wallet(self, request):
        """
        GET /api/smartlink/payouts/wallet/
        Return current wallet balances using dedicated PublisherWalletSerializer.
        """
        from api.smartlink.models.billing import PublisherWallet
        wallet, _ = PublisherWallet.objects.get_or_create(publisher=request.user)
        return Response(PublisherWalletSerializer(wallet).data)

    # ── Publisher: summary ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """GET /api/smartlink/payouts/summary/ — aggregate payout summary."""
        from api.smartlink.models.billing import PayoutRecord
        from django.db.models import Sum, Count
        qs  = PayoutRecord.objects.filter(publisher=request.user)
        agg = qs.aggregate(
            total_gross=Sum('gross_amount'),
            total_net=Sum('net_amount'),
            total_records=Count('id'),
        )
        return Response({
            'total_gross_usd': str(agg['total_gross'] or 0),
            'total_net_usd':   str(agg['total_net']   or 0),
            'total_payouts':   agg['total_records'],
            'by_status': {
                row['status']: row['count']
                for row in qs.values('status').annotate(count=Count('id'))
            },
        })

    # ── Admin: batches ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get', 'post'], url_path='batches')
    def batches(self, request):
        """Admin: list or create payout batches."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        if request.method == 'GET':
            from api.smartlink.models.billing import PayoutBatch
            batches = PayoutBatch.objects.all().order_by('-created_at')[:50]
            return Response(PayoutBatchSerializer(batches, many=True).data)

        # POST — create batch
        serializer = PayoutBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        from api.smartlink.services.billing.BillingService import BillingService
        batch = BillingService().create_batch(
            label=d['label'],
            date_from=d['period_from'],
            date_to=d['period_to'],
            admin_user=request.user,
        )
        return Response(PayoutBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'],
            url_path=r'batches/(?P<batch_pk>[^/.]+)/approve')
    def approve_batch(self, request, batch_pk=None):
        """Admin: approve all calculated records in a batch."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        from api.smartlink.models.billing import PayoutBatch
        from django.shortcuts import get_object_or_404
        batch    = get_object_or_404(PayoutBatch, pk=batch_pk)
        from api.smartlink.services.billing.BillingService import BillingService
        approved = BillingService().approve_batch(batch, request.user)
        return Response({'approved': approved, 'batch': PayoutBatchSerializer(batch).data})

    @action(detail=False, methods=['post'],
            url_path=r'batches/(?P<batch_pk>[^/.]+)/mark-paid')
    def mark_batch_paid(self, request, batch_pk=None):
        """Admin: mark all approved records as paid (manual gateway)."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        from api.smartlink.models.billing import PayoutBatch
        from django.shortcuts import get_object_or_404
        batch = get_object_or_404(PayoutBatch, pk=batch_pk)
        from api.smartlink.services.billing.BillingService import BillingService
        paid = BillingService().mark_batch_paid(batch)
        return Response({'paid': paid})

    @action(detail=False, methods=['post'], url_path='calculate')
    def calculate(self, request):
        """Admin: calculate payout for a specific publisher."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        publisher_id = request.data.get('publisher_id')
        date_from    = request.data.get('date_from')
        date_to      = request.data.get('date_to')
        if not all([publisher_id, date_from, date_to]):
            return Response(
                {'detail': 'publisher_id, date_from, date_to required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from datetime import date as dt
        publisher = User.objects.get(pk=publisher_id)
        from api.smartlink.services.billing.BillingService import BillingService
        record = BillingService().calculate_payout(
            publisher,
            dt.fromisoformat(date_from),
            dt.fromisoformat(date_to),
            request.user,
        )
        if not record:
            return Response({'message': 'Below minimum threshold or no conversions.'})
        return Response(PayoutRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    # ── Admin: payment gateway ─────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='process-payment')
    def process_payment(self, request, pk=None):
        """
        Admin: send a single APPROVED payout record to its payment gateway.

        POST /api/smartlink/payouts/{id}/process-payment/

        Gateways (auto-detected from publisher payment_method):
          paypal  → PayPal Payouts API
          wise    → Wise Transfers API
          wire / crypto / payoneer → returns requires_manual=True
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        from api.smartlink.models.billing import PayoutRecord
        from django.shortcuts import get_object_or_404
        from api.smartlink.services.billing.BillingService import BillingService

        record = get_object_or_404(PayoutRecord, pk=pk)
        if record.status != PayoutRecord.Status.APPROVED:
            return Response(
                {
                    'detail': (
                        f"PayoutRecord is '{record.status}', not 'approved'. "
                        "Only APPROVED records can be sent to payment gateways."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result      = BillingService().process_payment(record)
        http_status = (
            status.HTTP_200_OK
            if result['success'] or result.get('requires_manual')
            else status.HTTP_502_BAD_GATEWAY
        )
        return Response(result, status=http_status)

    @action(detail=False, methods=['post'],
            url_path=r'batches/(?P<batch_pk>[^/.]+)/process-payments')
    def process_batch_payments(self, request, batch_pk=None):
        """
        Admin: process all APPROVED records in a batch via their payment gateways.

        POST /api/smartlink/payouts/batches/{id}/process-payments/
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        from api.smartlink.models.billing import PayoutBatch
        from django.shortcuts import get_object_or_404
        from api.smartlink.services.billing.BillingService import BillingService

        batch   = get_object_or_404(PayoutBatch, pk=batch_pk)
        summary = BillingService().process_batch_payments(batch)
        return Response(summary, status=status.HTTP_200_OK)

    # ── Invoice PDF ────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='invoice-pdf')
    def invoice_pdf(self, request, pk=None):
        """
        GET /api/smartlink/payouts/{id}/invoice-pdf/

        Generate and stream a PDF invoice for a payout record.

        Access rules:
          - Publisher can download their own payout invoices.
          - Admin can download any invoice.

        Returns:
          HTTP 200 with Content-Type: application/pdf
          HTTP 403 if attempting to access another publisher's invoice.
          HTTP 404 if payout record not found.
          HTTP 503 if reportlab is not installed.
        """
        from django.http import HttpResponse
        from django.shortcuts import get_object_or_404
        from api.smartlink.models.billing import PayoutRecord

        record = get_object_or_404(PayoutRecord, pk=pk)

        # Access control — publisher can only see their own invoices
        if not request.user.is_staff and record.publisher_id != request.user.pk:
            return Response(
                {'detail': 'You do not have permission to access this invoice.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from api.smartlink.services.billing.InvoicePDFService import InvoicePDFService
            pdf_bytes = InvoicePDFService().generate(record)
        except ImportError as exc:
            logger.error(f"Invoice PDF generation failed (missing library): {exc}")
            return Response(
                {
                    'detail': (
                        'PDF generation library (reportlab) is not installed. '
                        'Run: pip install reportlab'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            logger.exception(
                f"Invoice PDF generation failed: payout#{pk} — {exc}"
            )
            return Response(
                {'detail': f'PDF generation error: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        ref_short  = str(record.reference_id).replace('-', '').upper()[:12]
        filename   = f"SmartLink-Invoice-{ref_short}.pdf"
        response   = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length']      = str(len(pdf_bytes))
        logger.info(
            f"Invoice PDF served: payout#{pk} ref={record.reference_id} "
            f"user={request.user.pk} size={len(pdf_bytes)}B"
        )
        return response

    # ── PayPal Webhook ─────────────────────────────────────────────────────────

    @action(
        detail=False,
        methods=['post'],
        url_path='paypal-webhook',
        permission_classes=[],          # No auth — PayPal sends unsigned callbacks
        authentication_classes=[CsrfExemptSessionAuthentication],
    )
    def paypal_webhook(self, request):
        """
        POST /api/smartlink/payouts/paypal-webhook/

        Receive and process PayPal IPN / Payouts webhook events.

        PayPal calls this URL when a payout batch status changes.
        We verify the event via PayPal's webhook verification API,
        then update the matching PayoutRecord status.

        Supported event_types:
          PAYMENT.PAYOUTSBATCH.SUCCESS   → mark records PAID
          PAYMENT.PAYOUTSBATCH.DENIED    → mark records FAILED
          PAYMENT.PAYOUTS-ITEM.SUCCEEDED → mark individual record PAID
          PAYMENT.PAYOUTS-ITEM.FAILED    → mark individual record FAILED
          PAYMENT.PAYOUTS-ITEM.BLOCKED   → mark individual record FAILED
          PAYMENT.PAYOUTS-ITEM.UNCLAIMED → mark individual record ON_HOLD

        PayPal docs:
          https://developer.paypal.com/api/rest/webhooks/
        """
        import json
        import hmac
        import hashlib
        from django.conf import settings as dj_settings
        from api.smartlink.models.billing import PayoutRecord

        raw_body = request.body

        # ── Optional webhook signature verification ─────────────────────────
        webhook_id = getattr(dj_settings, 'SMARTLINK_PAYPAL_WEBHOOK_ID', '')
        if webhook_id:
            verified = self._verify_paypal_webhook(request, raw_body, webhook_id)
            if not verified:
                logger.warning(
                    "PayPal webhook signature verification FAILED — "
                    "request rejected."
                )
                return Response(
                    {'detail': 'Webhook signature verification failed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Parse payload ───────────────────────────────────────────────────
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"PayPal webhook: invalid JSON body — {exc}")
            return Response(
                {'detail': 'Invalid JSON payload.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_type = payload.get('event_type', '')
        resource   = payload.get('resource', {})

        logger.info(f"PayPal webhook received: event_type={event_type}")

        # ── Route by event type ─────────────────────────────────────────────

        # Batch-level events — mark all records in that batch
        if event_type == 'PAYMENT.PAYOUTSBATCH.SUCCESS':
            batch_id = resource.get('batch_header', {}).get('payout_batch_id', '')
            if batch_id:
                updated = PayoutRecord.objects.filter(
                    transaction_ref=batch_id,
                    status=PayoutRecord.Status.PROCESSING,
                ).update(status=PayoutRecord.Status.PAID)
                logger.info(
                    f"PayPal BATCH SUCCESS: batch_id={batch_id} updated={updated} records"
                )
            return Response({'received': True, 'event_type': event_type})

        if event_type == 'PAYMENT.PAYOUTSBATCH.DENIED':
            batch_id = resource.get('batch_header', {}).get('payout_batch_id', '')
            reason   = resource.get('batch_header', {}).get('errors', [{}])
            reason_str = str(reason[0]) if reason else 'PayPal batch denied'
            if batch_id:
                records = PayoutRecord.objects.filter(transaction_ref=batch_id)
                for rec in records:
                    rec.mark_failed(reason=reason_str)
                logger.warning(
                    f"PayPal BATCH DENIED: batch_id={batch_id} reason={reason_str}"
                )
            return Response({'received': True, 'event_type': event_type})

        # Item-level events — match by sender_item_id (= our reference_id UUID)
        sender_item_id = (
            resource.get('payout_item', {}).get('sender_item_id', '')
            or resource.get('sender_item_id', '')
        )
        transaction_id = (
            resource.get('transaction_id', '')
            or resource.get('payout_item_id', '')
        )

        if not sender_item_id:
            logger.warning(
                f"PayPal webhook: no sender_item_id in event_type={event_type} — ignoring"
            )
            return Response({'received': True, 'event_type': event_type})

        try:
            import uuid as _uuid
            ref_uuid = _uuid.UUID(str(sender_item_id))
            record   = PayoutRecord.objects.get(reference_id=ref_uuid)
        except (ValueError, PayoutRecord.DoesNotExist):
            logger.warning(
                f"PayPal webhook: PayoutRecord not found for "
                f"sender_item_id={sender_item_id} event_type={event_type}"
            )
            # Return 200 so PayPal does not retry — the item may belong to another system
            return Response({'received': True, 'event_type': event_type})

        if event_type == 'PAYMENT.PAYOUTS-ITEM.SUCCEEDED':
            record.mark_paid(transaction_ref=transaction_id)
            logger.info(
                f"PayPal ITEM SUCCEEDED: ref={sender_item_id} txn={transaction_id}"
            )

        elif event_type in (
            'PAYMENT.PAYOUTS-ITEM.FAILED',
            'PAYMENT.PAYOUTS-ITEM.BLOCKED',
        ):
            errors = resource.get('errors', {})
            reason = errors.get('message', event_type)
            record.mark_failed(reason=reason)
            logger.warning(
                f"PayPal ITEM FAILED/BLOCKED: ref={sender_item_id} reason={reason}"
            )

        elif event_type == 'PAYMENT.PAYOUTS-ITEM.UNCLAIMED':
            # Receiver email not registered with PayPal — put on hold
            PayoutRecord.objects.filter(pk=record.pk).update(
                status=PayoutRecord.Status.ON_HOLD,
                failure_reason='PayPal: payout unclaimed — receiver email not registered.',
            )
            logger.warning(
                f"PayPal ITEM UNCLAIMED: ref={sender_item_id}"
            )

        elif event_type == 'PAYMENT.PAYOUTS-ITEM.RETURNED':
            # Funds returned — revert to APPROVED so admin can retry
            PayoutRecord.objects.filter(pk=record.pk).update(
                status=PayoutRecord.Status.APPROVED,
                failure_reason='PayPal: payout returned to sender — marked for retry.',
            )
            logger.warning(
                f"PayPal ITEM RETURNED: ref={sender_item_id}"
            )

        else:
            logger.debug(
                f"PayPal webhook: unhandled event_type={event_type} — acknowledged"
            )

        return Response({'received': True, 'event_type': event_type})

    @staticmethod
    def _verify_paypal_webhook(request, raw_body: bytes, webhook_id: str) -> bool:
        """
        Verify a PayPal webhook signature using PayPal's verification API.
        Returns True if the signature is valid, False otherwise.

        Calls POST /v1/notifications/verify-webhook-signature on PayPal's API.
        Falls back to True (unverified pass-through) if credentials are missing —
        log a warning in that case.

        PayPal docs:
          https://developer.paypal.com/api/rest/webhooks/rest/#link-verifywebhooksignature
        """
        import json
        import requests as _requests
        from django.conf import settings as dj_settings

        client_id     = getattr(dj_settings, 'SMARTLINK_PAYPAL_CLIENT_ID', '')
        client_secret = getattr(dj_settings, 'SMARTLINK_PAYPAL_CLIENT_SECRET', '')
        mode          = getattr(dj_settings, 'SMARTLINK_PAYPAL_MODE', 'sandbox')

        if not client_id or not client_secret:
            logger.warning(
                "PayPal webhook verification skipped — "
                "SMARTLINK_PAYPAL_CLIENT_ID / SMARTLINK_PAYPAL_CLIENT_SECRET not set."
            )
            return True  # Fail-open; operator must set credentials for production

        base_url = (
            "https://api-m.paypal.com"
            if mode == 'live'
            else "https://api-m.sandbox.paypal.com"
        )

        try:
            # Acquire token
            token_resp = _requests.post(
                f"{base_url}/v1/oauth2/token",
                auth=(client_id, client_secret),
                data={'grant_type': 'client_credentials'},
                timeout=10,
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()['access_token']

            # Build verification body
            verification_body = {
                'auth_algo':         request.headers.get('PAYPAL-AUTH-ALGO', ''),
                'cert_url':          request.headers.get('PAYPAL-CERT-URL', ''),
                'transmission_id':   request.headers.get('PAYPAL-TRANSMISSION-ID', ''),
                'transmission_sig':  request.headers.get('PAYPAL-TRANSMISSION-SIG', ''),
                'transmission_time': request.headers.get('PAYPAL-TRANSMISSION-TIME', ''),
                'webhook_id':        webhook_id,
                'webhook_event':     json.loads(raw_body),
            }
            verify_resp = _requests.post(
                f"{base_url}/v1/notifications/verify-webhook-signature",
                json=verification_body,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type':  'application/json',
                },
                timeout=10,
            )
            verify_resp.raise_for_status()
            result = verify_resp.json().get('verification_status', '')
            return result == 'SUCCESS'

        except Exception as exc:
            logger.error(f"PayPal webhook verification request failed: {exc}")
            return False  # Fail-closed on errors

    # ── Wise Webhook ───────────────────────────────────────────────────────────

    @action(
        detail=False,
        methods=['post'],
        url_path='wise-webhook',
        permission_classes=[],
        authentication_classes=[CsrfExemptSessionAuthentication],
    )
    def wise_webhook(self, request):
        """
        POST /api/smartlink/payouts/wise-webhook/

        Receive and process Wise (TransferWise) transfer webhook events.

        Wise calls this URL when a transfer state changes.
        We verify the X-Signature-SHA256 header using our Wise webhook
        public key (or shared secret), then update the matching PayoutRecord.

        Supported event types:
          transfers#state-change  with current_state=outgoing_payment_sent → PAID
          transfers#state-change  with current_state=funds_refunded         → FAILED/re-queue
          transfers#state-change  with current_state=cancelled              → FAILED
          transfers#state-change  with current_state=bounced_back           → FAILED

        Wise docs:
          https://docs.wise.com/api-docs/features/webhooks-notifications
        """
        import json
        import hashlib
        import hmac
        from api.smartlink.models.billing import PayoutRecord
        from django.conf import settings as dj_settings

        raw_body = request.body

        # ── Optional HMAC signature verification ────────────────────────────
        wise_secret = getattr(dj_settings, 'SMARTLINK_WISE_WEBHOOK_SECRET', '')
        if wise_secret:
            verified = self._verify_wise_webhook(request, raw_body, wise_secret)
            if not verified:
                logger.warning(
                    "Wise webhook X-Signature-SHA256 verification FAILED — "
                    "request rejected."
                )
                return Response(
                    {'detail': 'Webhook signature verification failed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Parse payload ────────────────────────────────────────────────────
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"Wise webhook: invalid JSON body — {exc}")
            return Response(
                {'detail': 'Invalid JSON payload.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_type = payload.get('event_type', '')
        data       = payload.get('data', {})

        logger.info(f"Wise webhook received: event_type={event_type}")

        # ── Only process transfer state-change events ────────────────────────
        if event_type != 'transfers#state-change':
            logger.debug(f"Wise webhook: unhandled event_type={event_type} — acknowledged")
            return Response({'received': True, 'event_type': event_type})

        resource       = data.get('resource', {})
        transfer_id    = str(resource.get('id', ''))
        current_state  = data.get('current_state', '')
        previous_state = data.get('previous_state', '')

        logger.info(
            f"Wise transfer#{transfer_id}: "
            f"{previous_state} → {current_state}"
        )

        if not transfer_id:
            logger.warning("Wise webhook: missing transfer id — ignoring")
            return Response({'received': True, 'event_type': event_type})

        # Locate matching PayoutRecord by transaction_ref (= Wise transfer_id string)
        record = PayoutRecord.objects.filter(
            transaction_ref=transfer_id,
            payment_method=PayoutRecord.PaymentMethod.WISE,
        ).first()

        if record is None:
            logger.warning(
                f"Wise webhook: no PayoutRecord found for transfer_id={transfer_id} "
                f"state={current_state} — may have been processed already or is unknown"
            )
            return Response({'received': True, 'event_type': event_type})

        # ── State transitions ────────────────────────────────────────────────
        if current_state == 'outgoing_payment_sent':
            # Transfer is on its way to the recipient's bank
            record.mark_paid(transaction_ref=transfer_id)
            logger.info(
                f"Wise PAYMENT SENT: transfer#{transfer_id} "
                f"payout#{record.pk} ref={record.reference_id}"
            )

        elif current_state == 'funds_refunded':
            # Transfer was returned — put back to APPROVED so admin can retry
            PayoutRecord.objects.filter(pk=record.pk).update(
                status=PayoutRecord.Status.APPROVED,
                failure_reason=(
                    f'Wise: funds refunded from transfer #{transfer_id}. '
                    'Please verify recipient details and retry.'
                ),
            )
            logger.warning(
                f"Wise FUNDS REFUNDED: transfer#{transfer_id} payout#{record.pk}"
            )

        elif current_state in ('cancelled', 'bounced_back', 'unknown'):
            reason_map = {
                'cancelled':   'Wise: transfer was cancelled.',
                'bounced_back': 'Wise: transfer bounced back — invalid recipient details.',
                'unknown':     'Wise: transfer entered unknown state.',
            }
            record.mark_failed(reason=reason_map.get(current_state, current_state))
            logger.warning(
                f"Wise TRANSFER FAILED: transfer#{transfer_id} "
                f"state={current_state} payout#{record.pk}"
            )

        elif current_state == 'processing':
            # Intermediate state — update to PROCESSING if still in APPROVED
            PayoutRecord.objects.filter(
                pk=record.pk,
                status=PayoutRecord.Status.APPROVED,
            ).update(status=PayoutRecord.Status.PROCESSING)
            logger.debug(
                f"Wise PROCESSING: transfer#{transfer_id} payout#{record.pk}"
            )

        else:
            logger.debug(
                f"Wise webhook: unhandled state={current_state} "
                f"transfer#{transfer_id} — no action taken"
            )

        return Response({'received': True, 'event_type': event_type})

    @staticmethod
    def _verify_wise_webhook(request, raw_body: bytes, wise_secret: str) -> bool:
        """
        Verify Wise webhook using X-Signature-SHA256 HMAC header.

        Wise signs each webhook request body with HMAC-SHA256 using the
        webhook shared secret configured in the Wise developer portal.

        Wise docs:
          https://docs.wise.com/api-docs/features/webhooks-notifications#x-signature-sha256
        """
        import hmac
        import hashlib
        import base64

        signature_header = (
            request.headers.get('X-Signature-SHA256', '')
            or request.headers.get('x-signature-sha256', '')
        )
        if not signature_header:
            logger.warning(
                "Wise webhook: X-Signature-SHA256 header missing — verification failed"
            )
            return False

        try:
            expected_mac = hmac.new(
                key=wise_secret.encode('utf-8'),
                msg=raw_body,
                digestmod=hashlib.sha256,
            ).digest()
            expected_b64 = base64.b64encode(expected_mac).decode('utf-8')
            return hmac.compare_digest(expected_b64, signature_header)
        except Exception as exc:
            logger.error(f"Wise webhook HMAC verification error: {exc}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Publisher Profile ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PublisherProfileViewSet(viewsets.ViewSet):
    """
    Publisher profile management.

    Publisher:
      GET   /api/smartlink/publisher/profile/my-profile/      — get own profile
      PUT   /api/smartlink/publisher/profile/my-profile/      — update own profile
      PATCH /api/smartlink/publisher/profile/my-profile/      — partial update
      POST  /api/smartlink/publisher/profile/gdpr-consent/    — record GDPR consent
      POST  /api/smartlink/publisher/profile/anonymize/       — GDPR right-to-erasure

    Admin:
      GET   /api/smartlink/publisher/profile/  (list) — all publisher profiles
    """
    permission_classes = [IsAuthenticated]

    def _get_or_create_profile(self, user):
        from api.smartlink.models.billing import PublisherProfile
        profile, _ = PublisherProfile.objects.get_or_create(publisher=user)
        return profile

    def list(self, request):
        """Admin: GET /api/smartlink/publisher/profile/ — all publisher profiles."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        from api.smartlink.models.billing import PublisherProfile
        profiles = PublisherProfile.objects.select_related('publisher').order_by('-created_at')
        serializer_class = PublisherProfileAdminSerializer
        return Response(serializer_class(profiles, many=True).data)

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='my-profile')
    def my_profile(self, request):
        """GET/PUT/PATCH /api/smartlink/publisher/profile/my-profile/"""
        profile = self._get_or_create_profile(request.user)
        if request.method == 'GET':
            return Response(PublisherProfileSerializer(profile).data)
        serializer = PublisherProfileSerializer(
            profile,
            data=request.data,
            partial=(request.method == 'PATCH'),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='gdpr-consent')
    def gdpr_consent(self, request):
        """POST /api/smartlink/publisher/profile/gdpr-consent/ — record GDPR consent."""
        from django.utils import timezone
        from api.smartlink.models.billing import PublisherProfile
        profile = self._get_or_create_profile(request.user)
        PublisherProfile.objects.filter(pk=profile.pk).update(
            gdpr_consent=True,
            gdpr_consent_at=timezone.now(),
        )
        return Response({'message': 'GDPR consent recorded.', 'timestamp': timezone.now()})

    @action(detail=False, methods=['post'])
    def anonymize(self, request):
        """
        POST /api/smartlink/publisher/profile/anonymize/
        GDPR right to erasure — anonymize all PII. IRREVERSIBLE.
        Requires: {"confirm": "DELETE MY DATA"}
        """
        if request.data.get('confirm') != 'DELETE MY DATA':
            return Response(
                {'detail': 'Send {"confirm": "DELETE MY DATA"} to confirm erasure.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile = self._get_or_create_profile(request.user)
        profile.anonymize()
        logger.warning(f"GDPR anonymization: user#{request.user.pk}")
        return Response({'message': 'Personal data anonymized. This action cannot be undone.'})
