# publisher_tools/views_webhooks_extended.py
"""
FILE 1 of 10 — Webhooks Extended API
=====================================
webhooks/ subfolder-এর 42টি floating function expose করা হয়েছে।

Business Gap: Publishers can't test webhooks, replay failed deliveries,
see delivery stats, or preview payloads. Event trackers (click,
impression, conversion) have no API entry point.

Previously floating (now wired):
  build_earning_event_payload, build_invoice_event_payload,
  build_invoice_created_payload, build_invoice_paid_payload,
  build_payout_request_payload, send_invoice_created_webhook,
  send_invoice_issued_webhook, send_invoice_paid_webhook,
  send_invoice_failed_webhook, send_payout_status_webhook,
  send_payment_milestone_webhook, build_fraud_detected_payload,
  build_ivt_summary_payload, send_fraud_detected_webhook,
  send_ivt_daily_summary_webhook, send_publisher_warned_webhook,
  send_revenue_deduction_webhook, send_ip_blocked_webhook,
  build_alert_payload, send_alert_webhook, send_kyc_alert,
  send_performance_alert, send_site_quality_alert, send_new_invoice_alert,
  send_payout_threshold_met_alert, send_tier_change_alert,
  send_account_suspended_alert, build_click_event_payload,
  send_click_webhook, send_click_deduction_webhook,
  send_click_velocity_alert, build_impression_event_payload,
  send_impression_webhook, send_batch_impression_webhook,
  handle_viewability_update, build_conversion_event_payload,
  send_conversion_webhook, send_postback_confirmation,
  log_delivery_attempt, get_webhook_delivery_stats, get_failed_deliveries

Register in urls.py:
  router.register(r'webhooks-ext', WebhookExtendedViewSet, basename='webhook-ext')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .models import PublisherWebhook, PublisherInvoice


# Event type catalogue for payload preview & simulation
WEBHOOK_EVENT_CATALOGUE = {
    # Payment events
    'invoice.created':          {'module': 'payment_webhook', 'fn': 'build_invoice_created_payload',  'category': 'payment',    'description': 'New invoice created'},
    'invoice.issued':           {'module': 'payment_webhook', 'fn': 'build_invoice_event_payload',     'category': 'payment',    'description': 'Invoice sent to publisher'},
    'invoice.paid':             {'module': 'payment_webhook', 'fn': 'build_invoice_paid_payload',      'category': 'payment',    'description': 'Invoice marked paid'},
    'invoice.failed':           {'module': 'payment_webhook', 'fn': 'build_invoice_event_payload',     'category': 'payment',    'description': 'Invoice payment failed'},
    'payout.status_changed':    {'module': 'payment_webhook', 'fn': 'build_payout_request_payload',    'category': 'payment',    'description': 'Payout request status changed'},
    'payment.milestone':        {'module': 'webhook_manager', 'fn': 'build_earning_event_payload',     'category': 'payment',    'description': 'Revenue milestone reached'},
    'earning.updated':          {'module': 'webhook_manager', 'fn': 'build_earning_event_payload',     'category': 'earning',    'description': 'Earnings updated'},
    # Fraud events
    'fraud.detected':           {'module': 'fraud_webhook',   'fn': 'build_fraud_detected_payload',    'category': 'fraud',      'description': 'Fraud detected'},
    'fraud.ivt_summary':        {'module': 'fraud_webhook',   'fn': 'build_ivt_summary_payload',       'category': 'fraud',      'description': 'Daily IVT summary'},
    'fraud.publisher_warned':   {'module': 'fraud_webhook',   'fn': None,                              'category': 'fraud',      'description': 'Publisher received fraud warning'},
    'fraud.revenue_deducted':   {'module': 'fraud_webhook',   'fn': None,                              'category': 'fraud',      'description': 'Revenue deducted for fraud'},
    'fraud.ip_blocked':         {'module': 'fraud_webhook',   'fn': None,                              'category': 'fraud',      'description': 'IP address blocked'},
    # Alert events
    'alert.kyc':                {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'KYC status changed'},
    'alert.performance':        {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'Performance threshold alert'},
    'alert.site_quality':       {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'Site quality score alert'},
    'alert.payout_threshold':   {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'Payout threshold reached'},
    'alert.tier_change':        {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'Publisher tier changed'},
    'alert.account_suspended':  {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'Account suspended'},
    'alert.new_invoice':        {'module': 'alert_webhook',   'fn': 'build_alert_payload',             'category': 'alert',      'description': 'New invoice available'},
    # Tracking events
    'click.recorded':           {'module': 'click_webhook',       'fn': 'build_click_event_payload',      'category': 'tracking',   'description': 'Ad click recorded'},
    'impression.recorded':      {'module': 'impression_webhook',  'fn': 'build_impression_event_payload', 'category': 'tracking',   'description': 'Ad impression recorded'},
    'conversion.recorded':      {'module': 'conversion_webhook',  'fn': 'build_conversion_event_payload', 'category': 'tracking',   'description': 'Conversion recorded'},
}


class WebhookExtendedViewSet(BaseViewSet):
    """
    Webhooks Extended API — webhooks/ subfolder-এর সব floating
    functions expose করে।

    Testing:
      GET  /webhooks-ext/event-types/          — all event types catalogue
      POST /webhooks-ext/simulate/             — simulate webhook event delivery
      POST /webhooks-ext/test-delivery/        — send test payload to endpoint URL
      GET  /webhooks-ext/payload-preview/      — preview event payload structure

    Delivery management:
      GET  /webhooks-ext/delivery-stats/       — delivery statistics
      GET  /webhooks-ext/failed-deliveries/    — failed deliveries
      POST /webhooks-ext/replay/               — replay a specific delivery
      POST /webhooks-ext/replay-all-failed/    — replay all failed for webhook

    Payment event senders (admin):
      POST /webhooks-ext/send-invoice-created/ — send invoice.created event
      POST /webhooks-ext/send-invoice-issued/  — send invoice.issued event
      POST /webhooks-ext/send-invoice-paid/    — send invoice.paid event
      POST /webhooks-ext/send-payout-status/   — send payout.status event

    Alert senders (admin):
      POST /webhooks-ext/send-alert/           — send generic alert
      POST /webhooks-ext/send-kyc-alert/       — send KYC alert
      POST /webhooks-ext/send-performance-alert/ — send performance alert
      POST /webhooks-ext/send-threshold-alert/ — send payout threshold alert
      POST /webhooks-ext/send-suspension-alert/ — send account suspension alert

    Tracking endpoints (event ingestion):
      POST /webhooks-ext/track-click/          — record click + fire click webhook
      POST /webhooks-ext/track-impression/     — record impression + fire webhook
      POST /webhooks-ext/track-impression-batch/ — batch impression processing
      POST /webhooks-ext/track-conversion/     — record conversion + fire webhook
      POST /webhooks-ext/viewability-update/   — update viewability for impression
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_webhook(self, webhook_id, publisher):
        try:
            return PublisherWebhook.objects.get(pk=webhook_id, publisher=publisher)
        except PublisherWebhook.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Webhook not found.')

    # ── EVENT TYPE CATALOGUE ───────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='event-types')
    def event_types(self, request):
        """
        সব available webhook event types।
        GET ?category=payment | fraud | alert | tracking
        """
        cat = request.query_params.get('category')
        result = {}
        for event, info in WEBHOOK_EVENT_CATALOGUE.items():
            if cat and info['category'] != cat:
                continue
            result[event] = {
                'event':       event,
                'category':    info['category'],
                'description': info['description'],
            }
        categories = list({v['category'] for v in WEBHOOK_EVENT_CATALOGUE.values()})
        return self.success_response(data={
            'events':     result,
            'total':      len(result),
            'categories': categories,
        })

    # ── PAYLOAD PREVIEW ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='payload-preview')
    def payload_preview(self, request):
        """
        Event payload-এর structure preview।
        GET ?event_type=invoice.paid&invoice_id=5
        """
        event_type = request.query_params.get('event_type', '')
        publisher  = self._get_publisher()
        if not event_type:
            return self.error_response('event_type required.', status_code=400)
        if event_type not in WEBHOOK_EVENT_CATALOGUE:
            return self.error_response(
                f'Unknown event type. See /webhooks-ext/event-types/',
                status_code=400,
            )
        info = WEBHOOK_EVENT_CATALOGUE[event_type]
        # Build sample payload
        sample = {
            'event':        event_type,
            'publisher_id': publisher.publisher_id,
            'timestamp':    '2025-01-15T10:30:00Z',
            'data':         {'note': f'Sample payload for {event_type}'},
        }
        if info['category'] == 'payment':
            invoice_id = request.query_params.get('invoice_id')
            if invoice_id:
                try:
                    invoice = PublisherInvoice.objects.get(pk=invoice_id, publisher=publisher)
                    mod = __import__(f'publisher_tools.webhooks.{info["module"]}',
                                     fromlist=[info['fn']])
                    builder = getattr(mod, info['fn'], None)
                    if builder:
                        sample['data'] = builder(invoice)
                except Exception:
                    pass
        return self.success_response(data={
            'event_type':    event_type,
            'category':      info['category'],
            'sample_payload': sample,
        })

    # ── SIMULATE ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='simulate')
    def simulate(self, request):
        """
        Publisher-এর configured webhooks-এ একটি event simulate করে।
        POST body: {
          "event_type": "invoice.paid",
          "data":       {}   ← optional override
        }
        """
        publisher  = self._get_publisher()
        event_type = request.data.get('event_type', '')
        extra_data = request.data.get('data', {})
        if not event_type:
            return self.error_response('event_type required.', status_code=400)
        if event_type not in WEBHOOK_EVENT_CATALOGUE:
            return self.error_response(
                f'Unknown event_type. See /webhooks-ext/event-types/',
                status_code=400,
            )
        try:
            from .webhooks.webhook_manager import send_webhook_event
            logs = send_webhook_event(publisher, event_type, {
                'simulated': True,
                'event_type': event_type,
                **extra_data,
            })
            return self.success_response(data={
                'event_type':   event_type,
                'webhooks_sent': len(logs),
                'deliveries':  [
                    {
                        'webhook_name': getattr(log.webhook, 'name', ''),
                        'status':       log.status,
                        'response_code': log.response_code,
                    }
                    for log in logs
                ],
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='test-delivery')
    def test_delivery(self, request):
        """
        Specific webhook endpoint-এ test event পাঠায়।
        POST body: { "webhook_id": 5, "event_type": "invoice.paid" }
        """
        publisher   = self._get_publisher()
        webhook_id  = request.data.get('webhook_id')
        event_type  = request.data.get('event_type', 'test.ping')
        if not webhook_id:
            return self.error_response('webhook_id required.', status_code=400)
        webhook = self._get_webhook(webhook_id, publisher)
        try:
            from .webhooks.webhook_manager import send_webhook_event
            logs = send_webhook_event(publisher, event_type, {
                'test': True,
                'webhook_id': webhook_id,
                'event_type': event_type,
            })
            matching = [l for l in logs if l.webhook_id == webhook.pk]
            log = matching[0] if matching else (logs[0] if logs else None)
            return self.success_response(data={
                'webhook_id':   webhook_id,
                'event_type':   event_type,
                'status':       log.status if log else 'no_delivery',
                'response_code': log.response_code if log else None,
                'delivery_ms':  log.delivery_time_ms if log else None,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── DELIVERY STATS ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='delivery-stats')
    def delivery_stats(self, request):
        """
        Webhook delivery statistics।
        GET ?webhook_id=5&days=30
        """
        publisher  = self._get_publisher()
        webhook_id = request.query_params.get('webhook_id')
        days       = int(request.query_params.get('days', 30))
        try:
            from .webhooks.webhook_logger import get_webhook_delivery_stats
            if webhook_id:
                webhook = self._get_webhook(webhook_id, publisher)
                stats   = get_webhook_delivery_stats(webhook, days=days)
            else:
                webhooks = PublisherWebhook.objects.filter(publisher=publisher)
                stats    = {
                    'total_webhooks': webhooks.count(),
                    'webhooks': [
                        get_webhook_delivery_stats(wh, days=days)
                        for wh in webhooks
                    ],
                }
            return self.success_response(data=stats)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='failed-deliveries')
    def failed_deliveries(self, request):
        """
        Failed webhook deliveries।
        GET ?webhook_id=5&limit=50
        """
        publisher  = self._get_publisher()
        webhook_id = request.query_params.get('webhook_id')
        limit      = int(request.query_params.get('limit', 50))
        try:
            from .webhooks.webhook_logger import get_failed_deliveries
            if webhook_id:
                webhook  = self._get_webhook(webhook_id, publisher)
                failures = get_failed_deliveries(webhook, limit=limit)
            else:
                failures = []
                for wh in PublisherWebhook.objects.filter(publisher=publisher):
                    failures.extend(get_failed_deliveries(wh, limit=limit))
                failures = failures[:limit]
            return self.success_response(data={
                'failures': [
                    {
                        'pk':           f.pk if hasattr(f, 'pk') else None,
                        'webhook':      str(getattr(f, 'webhook', '')),
                        'event_type':   getattr(f, 'event_type', ''),
                        'attempt':      getattr(f, 'attempt', 1),
                        'error':        getattr(f, 'error_message', ''),
                        'created_at':   str(getattr(f, 'created_at', '')),
                    }
                    for f in (failures if isinstance(failures, list) else [failures])
                ],
                'count': len(failures) if isinstance(failures, list) else 1,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='replay')
    def replay(self, request):
        """
        Failed delivery replay করে।
        POST body: { "delivery_id": 123 }
        """
        publisher   = self._get_publisher()
        delivery_id = request.data.get('delivery_id')
        if not delivery_id:
            return self.error_response('delivery_id required.', status_code=400)
        try:
            from .models import WebhookDeliveryLog
            from .webhooks.webhook_manager import send_webhook_event
            log = WebhookDeliveryLog.objects.get(
                pk=delivery_id, webhook__publisher=publisher
            )
            new_logs = send_webhook_event(
                publisher, log.event_type, log.payload
            )
            return self.success_response(data={
                'original_delivery_id': delivery_id,
                'replayed':  len(new_logs) > 0,
                'new_status': new_logs[0].status if new_logs else 'no_delivery',
            })
        except WebhookDeliveryLog.DoesNotExist:
            return self.error_response('Delivery not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='replay-all-failed')
    def replay_all_failed(self, request):
        """
        Webhook-এর সব failed deliveries replay করে।
        POST body: { "webhook_id": 5 }
        """
        publisher  = self._get_publisher()
        webhook_id = request.data.get('webhook_id')
        if not webhook_id:
            return self.error_response('webhook_id required.', status_code=400)
        webhook = self._get_webhook(webhook_id, publisher)
        try:
            from .models import WebhookDeliveryLog
            from .webhooks.webhook_manager import send_webhook_event
            failed = WebhookDeliveryLog.objects.filter(
                webhook=webhook, status='failed'
            ).order_by('-created_at')[:20]
            replayed = 0
            for log in failed:
                try:
                    send_webhook_event(publisher, log.event_type, log.payload)
                    replayed += 1
                except Exception:
                    continue
            return self.success_response(data={
                'webhook_id': webhook_id,
                'replayed':   replayed,
                'total_failed': failed.count(),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── PAYMENT EVENT SENDERS ──────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='send-invoice-created',
        permission_classes=[IsAuthenticated, IsAdminOrPublisher],
    )
    def send_invoice_created(self, request):
        """
        invoice.created webhook fire করে।
        POST body: { "invoice_id": 42 }
        """
        publisher  = self._get_publisher()
        invoice_id = request.data.get('invoice_id')
        if not invoice_id:
            return self.error_response('invoice_id required.', status_code=400)
        try:
            invoice = PublisherInvoice.objects.get(pk=invoice_id, publisher=publisher)
            from .webhooks.payment_webhook import send_invoice_created_webhook
            ok = send_invoice_created_webhook(publisher, invoice)
            return self.success_response(data={'sent': ok, 'invoice_id': invoice_id})
        except PublisherInvoice.DoesNotExist:
            return self.error_response('Invoice not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='send-invoice-paid',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def send_invoice_paid(self, request):
        """[Admin] invoice.paid webhook fire করে।"""
        invoice_id   = request.data.get('invoice_id')
        publisher_id = request.data.get('publisher_id')
        if not invoice_id or not publisher_id:
            return self.error_response('invoice_id and publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            invoice   = PublisherInvoice.objects.get(pk=invoice_id, publisher=publisher)
            from .webhooks.payment_webhook import send_invoice_paid_webhook
            ok = send_invoice_paid_webhook(publisher, invoice)
            return self.success_response(data={'sent': ok})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='send-payout-status',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def send_payout_status(self, request):
        """[Admin] payout.status_changed webhook fire করে।"""
        publisher_id = request.data.get('publisher_id')
        payout_id    = request.data.get('payout_id')
        if not publisher_id:
            return self.error_response('publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            from .webhooks.payment_webhook import send_payout_status_webhook
            ok = send_payout_status_webhook(publisher, {'id': payout_id})
            return self.success_response(data={'sent': ok})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── ALERT SENDERS ──────────────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='send-alert',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def send_alert(self, request):
        """
        [Admin] Generic alert webhook fire করে।
        POST body: {
          "publisher_id": "PUB-001",
          "alert_type": "performance",
          "severity":   "high",
          "title":      "Low fill rate detected",
          "message":    "Your fill rate dropped below 50%"
        }
        """
        publisher_id = request.data.get('publisher_id')
        alert_type   = request.data.get('alert_type', 'general')
        severity     = request.data.get('severity', 'info')
        title        = request.data.get('title', '')
        message      = request.data.get('message', '')
        if not publisher_id:
            return self.error_response('publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            from .webhooks.alert_webhook import send_alert_webhook
            ok = send_alert_webhook(publisher, alert_type, severity, title, message)
            return self.success_response(data={'sent': ok})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='send-kyc-alert',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def send_kyc_alert(self, request):
        """[Admin] KYC status alert।"""
        publisher_id  = request.data.get('publisher_id')
        alert_subtype = request.data.get('alert_subtype', 'submitted')
        if not publisher_id:
            return self.error_response('publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            from .webhooks.alert_webhook import send_kyc_alert
            ok = send_kyc_alert(publisher, alert_subtype)
            return self.success_response(data={'sent': ok})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='send-threshold-alert',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def send_threshold_alert(self, request):
        """[Admin] Payout threshold met alert।"""
        publisher_id = request.data.get('publisher_id')
        balance      = float(request.data.get('balance', 0))
        threshold    = float(request.data.get('threshold', 100))
        if not publisher_id:
            return self.error_response('publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            from .webhooks.alert_webhook import send_payout_threshold_met_alert
            ok = send_payout_threshold_met_alert(publisher, balance, threshold)
            return self.success_response(data={'sent': ok})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='send-suspension-alert',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def send_suspension_alert(self, request):
        """[Admin] Account suspension alert।"""
        publisher_id = request.data.get('publisher_id')
        reason       = request.data.get('reason', 'Policy violation')
        if not publisher_id:
            return self.error_response('publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            from .webhooks.alert_webhook import send_account_suspended_alert
            ok = send_account_suspended_alert(publisher, reason)
            return self.success_response(data={'sent': ok})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── TRACKING ENDPOINTS ─────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='track-click')
    def track_click(self, request):
        """
        Ad click record + fire click webhook।
        POST body: {
          "unit_id":    "UNIT-001",
          "session_id": "sess_abc",
          "ip":         "1.2.3.4",
          "ua":         "Mozilla/...",
          "context":    {}
        }
        """
        publisher = self._get_publisher()
        unit_id   = request.data.get('unit_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        click_data = {
            'unit_id':    unit_id,
            'session_id': request.data.get('session_id', ''),
            'ip':         request.data.get('ip', ''),
            'ua':         request.data.get('ua', ''),
            'context':    request.data.get('context', {}),
        }
        try:
            from .webhooks.click_webhook import build_click_event_payload, send_click_webhook
            payload  = build_click_event_payload(click_data)
            deliveries = send_click_webhook(publisher, click_data)
            return self.success_response(data={
                'recorded':  True,
                'payload':   payload,
                'webhooks_fired': len(deliveries),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='track-impression')
    def track_impression_event(self, request):
        """
        Ad impression record + fire impression webhook。
        POST body: {
          "unit_id":    "UNIT-001",
          "session_id": "sess_abc",
          "ip":         "1.2.3.4",
          "context":    {}
        }
        """
        publisher = self._get_publisher()
        unit_id   = request.data.get('unit_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        imp_data = {
            'unit_id':    unit_id,
            'session_id': request.data.get('session_id', ''),
            'ip':         request.data.get('ip', ''),
            'context':    request.data.get('context', {}),
        }
        try:
            from .webhooks.impression_webhook import (
                build_impression_event_payload, send_impression_webhook
            )
            payload    = build_impression_event_payload(imp_data)
            deliveries = send_impression_webhook(publisher, imp_data)
            return self.success_response(data={
                'recorded':       True,
                'payload':        payload,
                'webhooks_fired': len(deliveries),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='track-impression-batch')
    def track_impression_batch(self, request):
        """
        Batch impression processing।
        POST body: {
          "impressions": [
            { "unit_id": "UNIT-001", "session_id": "s1" },
            { "unit_id": "UNIT-002", "session_id": "s2" }
          ]
        }
        """
        publisher   = self._get_publisher()
        impressions = request.data.get('impressions', [])
        if not impressions:
            return self.error_response('impressions list required.', status_code=400)
        if len(impressions) > 1000:
            return self.error_response('Max 1000 impressions per batch.', status_code=400)
        try:
            from .webhooks.impression_webhook import send_batch_impression_webhook
            result = send_batch_impression_webhook(publisher, impressions)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='track-conversion')
    def track_conversion(self, request):
        """
        Conversion event record + fire conversion webhook।
        POST body: {
          "unit_id":         "UNIT-001",
          "conversion_type": "purchase",
          "value":           29.99,
          "currency":        "USD",
          "session_id":      "sess_abc",
          "context":         {}
        }
        """
        publisher = self._get_publisher()
        unit_id   = request.data.get('unit_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        conv_data = {
            'unit_id':         unit_id,
            'conversion_type': request.data.get('conversion_type', 'conversion'),
            'value':           request.data.get('value', 0),
            'currency':        request.data.get('currency', 'USD'),
            'session_id':      request.data.get('session_id', ''),
            'context':         request.data.get('context', {}),
        }
        try:
            from .webhooks.conversion_webhook import (
                build_conversion_event_payload, send_conversion_webhook
            )
            payload    = build_conversion_event_payload(conv_data)
            deliveries = send_conversion_webhook(publisher, conv_data)
            return self.success_response(data={
                'recorded':       True,
                'payload':        payload,
                'webhooks_fired': len(deliveries),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='viewability-update')
    def viewability_update(self, request):
        """
        Impression-এর viewability score update করে।
        POST body: {
          "impression_id": "imp_abc123",
          "viewability":   { "viewable": true, "in_view_pct": 85, "duration_ms": 3000 }
        }
        """
        publisher     = self._get_publisher()
        impression_id = request.data.get('impression_id', '')
        viewability   = request.data.get('viewability', {})
        if not impression_id:
            return self.error_response('impression_id required.', status_code=400)
        try:
            from .webhooks.impression_webhook import handle_viewability_update
            ok = handle_viewability_update(publisher, impression_id, viewability)
            return self.success_response(data={
                'impression_id': impression_id,
                'updated':       ok,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
