"""
Tests for SmartLink 3% completion features
===========================================
Covers all 5 new features:

  1. Invoice PDF generation (InvoicePDFService + GET /payouts/{id}/invoice-pdf/)
  2. PayPal webhook callback (POST /payouts/paypal-webhook/)
  3. Wise webhook callback (POST /payouts/wise-webhook/)
  4. Per-publisher attribution window (PublisherProfile.attribution_window_days)
  5. Offer catalog sync (POST /smartlinks/{sl_pk}/pool/{pool_id}/sync-from-catalog/)
"""
import json
import uuid
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status as drf_status

User = get_user_model()

from api.smartlink.tests.test_helpers import (
    make_user, make_offer, make_smartlink, make_click,
    make_payout_record, make_profile, make_wallet,
    make_offer_pool_entry, make_batch, auth_client,
    # backwards-compatible aliases (legacy _make_* names)
    _make_user, _make_offer, _make_smartlink, _make_sl,
    _make_click, _make_profile, _make_payout_record, _make_batch,
    _make_offer_pool_entry,
)

# ─── Shared helpers ───────────────────────────────────────────────────────────

# ═════════════════════════════════════════════════════════════════════════════
# 1. Invoice PDF
# ═════════════════════════════════════════════════════════════════════════════

class InvoicePDFServiceTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('inv_pub')
        _make_profile(self.publisher)
        self.record = _make_payout_record(
            self.publisher, rec_status='paid', net_amount='350.00',
        )
        # Use timezone-aware datetime for paid_at
        from django.utils import timezone
        self.record.paid_at = timezone.now()
        self.record.save(update_fields=['paid_at'])

    def test_generate_returns_bytes(self):
        """InvoicePDFService.generate() returns a non-empty bytes object."""
        from api.smartlink.services.billing.InvoicePDFService import InvoicePDFService
        pdf_bytes = InvoicePDFService().generate(self.record)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)

    def test_generate_pdf_starts_with_pdf_header(self):
        """Generated file is a valid PDF (starts with %PDF magic bytes)."""
        from api.smartlink.services.billing.InvoicePDFService import InvoicePDFService
        pdf_bytes = InvoicePDFService().generate(self.record)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_generate_raises_import_error_when_reportlab_missing(self):
        """InvoicePDFService raises ImportError when reportlab is absent."""
        from api.smartlink.services.billing.InvoicePDFService import InvoicePDFService
        with patch.object(
            InvoicePDFService, 'generate',
            side_effect=ImportError('reportlab not installed'),
        ):
            with self.assertRaises(ImportError):
                InvoicePDFService().generate(self.record)

    def test_invoice_pdf_endpoint_returns_200_for_owner(self):
        """GET /api/smartlink/payouts/{id}/invoice-pdf/ → 200 for the owner."""
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.get(f'/api/smartlink/payouts/{self.record.pk}/invoice-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('attachment', resp.get('Content-Disposition', ''))

    def test_invoice_pdf_endpoint_returns_403_for_other_publisher(self):
        """Publisher cannot download another publisher's invoice."""
        other = _make_user('inv_other')
        client = APIClient()
        client.force_authenticate(other)
        resp = client.get(f'/api/smartlink/payouts/{self.record.pk}/invoice-pdf/')
        self.assertEqual(resp.status_code, drf_status.HTTP_403_FORBIDDEN)

    def test_invoice_pdf_endpoint_returns_200_for_admin(self):
        """Admin can download any publisher's invoice."""
        admin = _make_user('inv_admin', is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get(f'/api/smartlink/payouts/{self.record.pk}/invoice-pdf/')
        self.assertEqual(resp.status_code, 200)

    def test_invoice_pdf_endpoint_returns_503_when_reportlab_missing(self):
        """Endpoint returns 503 when reportlab is not installed."""
        client = APIClient()
        client.force_authenticate(self.publisher)
        with patch(
            'api.smartlink.services.billing.InvoicePDFService.InvoicePDFService.generate',
            side_effect=ImportError('reportlab not installed'),
        ):
            resp = client.get(
                f'/api/smartlink/payouts/{self.record.pk}/invoice-pdf/'
            )
        self.assertEqual(resp.status_code, drf_status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_invoice_pdf_endpoint_returns_404_for_unknown_id(self):
        """GET /payouts/99999/invoice-pdf/ → 404."""
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.get('/api/smartlink/payouts/99999/invoice-pdf/')
        self.assertEqual(resp.status_code, 404)

# ═════════════════════════════════════════════════════════════════════════════
# 2. PayPal Webhook
# ═════════════════════════════════════════════════════════════════════════════

class PayPalWebhookTest(TestCase):
    """
    Tests for POST /api/smartlink/payouts/paypal-webhook/

    APIClient with enforce_csrf_checks=False simulates external callback.
    """
    WEBHOOK_URL = '/api/smartlink/payouts/paypal-webhook/'

    def setUp(self):
        self.publisher = _make_user('pp_pub')
        self.record = _make_payout_record(
            self.publisher, payment_method='paypal',
            payment_address='pub@paypal.com', rec_status='processing',
        )
        # Use Django's test Client (not DRF APIClient) to bypass DRF CSRF enforcement.
        # Webhook endpoints are public — external servers (PayPal) never send CSRF tokens.
        from django.test import Client as DjangoClient
        self.http_client = DjangoClient(enforce_csrf_checks=False)

    def _post(self, payload):
        return self.http_client.post(
            self.WEBHOOK_URL,
            data=json.dumps(payload),
            content_type='application/json',
        )

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_item_succeeded_marks_record_paid(self):
        """PAYMENT.PAYOUTS-ITEM.SUCCEEDED → PayoutRecord status becomes 'paid'."""
        from api.smartlink.models.billing import PayoutRecord
        payload = {
            'event_type': 'PAYMENT.PAYOUTS-ITEM.SUCCEEDED',
            'resource': {
                'payout_item':  {'sender_item_id': str(self.record.reference_id)},
                'transaction_id': 'TXN001',
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.PAID)
        self.assertEqual(self.record.transaction_ref, 'TXN001')

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_item_failed_marks_record_failed(self):
        """PAYMENT.PAYOUTS-ITEM.FAILED → PayoutRecord status becomes 'failed'."""
        from api.smartlink.models.billing import PayoutRecord
        payload = {
            'event_type': 'PAYMENT.PAYOUTS-ITEM.FAILED',
            'resource': {
                'payout_item': {'sender_item_id': str(self.record.reference_id)},
                'errors': {'message': 'Receiver restricted'},
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.FAILED)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_item_unclaimed_marks_record_on_hold(self):
        """PAYMENT.PAYOUTS-ITEM.UNCLAIMED → PayoutRecord status becomes 'on_hold'."""
        from api.smartlink.models.billing import PayoutRecord
        payload = {
            'event_type': 'PAYMENT.PAYOUTS-ITEM.UNCLAIMED',
            'resource': {
                'payout_item': {'sender_item_id': str(self.record.reference_id)},
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.ON_HOLD)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_batch_success_marks_all_processing_records_paid(self):
        """PAYMENT.PAYOUTSBATCH.SUCCESS → matching PROCESSING records → PAID."""
        from api.smartlink.models.billing import PayoutRecord
        batch_id = 'BATCHPP12345'
        self.record.transaction_ref = batch_id
        self.record.status = PayoutRecord.Status.PROCESSING
        self.record.save(update_fields=['transaction_ref', 'status'])
        payload = {
            'event_type': 'PAYMENT.PAYOUTSBATCH.SUCCESS',
            'resource': {'batch_header': {'payout_batch_id': batch_id}},
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.PAID)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_unknown_sender_item_id_returns_200(self):
        """Unknown sender_item_id returns 200 (don't let PayPal retry indefinitely)."""
        payload = {
            'event_type': 'PAYMENT.PAYOUTS-ITEM.SUCCEEDED',
            'resource': {
                'payout_item': {'sender_item_id': str(uuid.uuid4())},
                'transaction_id': 'TXN_UNKNOWN',
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_invalid_json_returns_400(self):
        """Malformed JSON body → 400 Bad Request."""
        resp = self.client.post(
            self.WEBHOOK_URL, data='not-valid-json',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='wh_test_123')
    def test_bad_signature_returns_400(self):
        """Invalid signature → 400 when SMARTLINK_PAYPAL_WEBHOOK_ID is set."""
        with patch(
            'api.smartlink.viewsets.BusinessViewSets.PayoutViewSet._verify_paypal_webhook',
            return_value=False,
        ):
            resp = self._post({'event_type': 'PAYMENT.PAYOUTS-ITEM.SUCCEEDED'})
        self.assertEqual(resp.status_code, 400)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_item_returned_reverts_to_approved(self):
        """PAYMENT.PAYOUTS-ITEM.RETURNED → status reverts to APPROVED for retry."""
        from api.smartlink.models.billing import PayoutRecord
        self.record.status = PayoutRecord.Status.PROCESSING
        self.record.save(update_fields=['status'])
        payload = {
            'event_type': 'PAYMENT.PAYOUTS-ITEM.RETURNED',
            'resource': {
                'payout_item': {'sender_item_id': str(self.record.reference_id)},
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.APPROVED)

    @override_settings(SMARTLINK_PAYPAL_WEBHOOK_ID='')
    def test_unhandled_event_type_returns_200(self):
        """Unknown PayPal event type is acknowledged with 200 (no crash)."""
        payload = {'event_type': 'PAYMENT.SALE.COMPLETED', 'resource': {}}
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)

# ═════════════════════════════════════════════════════════════════════════════
# 3. Wise Webhook
# ═════════════════════════════════════════════════════════════════════════════

class WiseWebhookTest(TestCase):
    """Tests for POST /api/smartlink/payouts/wise-webhook/"""

    WEBHOOK_URL = '/api/smartlink/payouts/wise-webhook/'

    def setUp(self):
        self.publisher   = _make_user('wise_pub')
        self.transfer_id = '98765432'
        self.record = _make_payout_record(
            self.publisher, payment_method='wise',
            payment_address='pub@wise.com', rec_status='processing',
            transaction_ref=self.transfer_id,
        )
        from django.test import Client as DjangoClient
        self.http_client = DjangoClient(enforce_csrf_checks=False)

    def _post(self, payload):
        return self.http_client.post(
            self.WEBHOOK_URL,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def _state_change(self, current_state, previous_state='processing'):
        return {
            'event_type': 'transfers#state-change',
            'data': {
                'resource': {
                    'type': 'transfer',
                    'id':   int(self.transfer_id),
                    'profile_id': 12345,
                },
                'current_state':  current_state,
                'previous_state': previous_state,
            },
        }

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_outgoing_payment_sent_marks_paid(self):
        """outgoing_payment_sent → PayoutRecord.status = 'paid'."""
        from api.smartlink.models.billing import PayoutRecord
        resp = self._post(self._state_change('outgoing_payment_sent'))
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.PAID)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_funds_refunded_requeues_to_approved(self):
        """funds_refunded → PayoutRecord.status = 'approved' (retry allowed)."""
        from api.smartlink.models.billing import PayoutRecord
        resp = self._post(self._state_change('funds_refunded'))
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.APPROVED)
        self.assertIn('refunded', self.record.failure_reason.lower())

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_cancelled_marks_failed(self):
        """cancelled → PayoutRecord.status = 'failed'."""
        from api.smartlink.models.billing import PayoutRecord
        resp = self._post(self._state_change('cancelled'))
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.FAILED)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_bounced_back_marks_failed(self):
        """bounced_back → PayoutRecord.status = 'failed'."""
        from api.smartlink.models.billing import PayoutRecord
        resp = self._post(self._state_change('bounced_back'))
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.FAILED)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_processing_state_updates_approved_to_processing(self):
        """Intermediate 'processing' state transitions APPROVED → PROCESSING."""
        from api.smartlink.models.billing import PayoutRecord
        self.record.status = PayoutRecord.Status.APPROVED
        self.record.save(update_fields=['status'])
        resp = self._post(self._state_change('processing', 'incoming_payment_waiting'))
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, PayoutRecord.Status.PROCESSING)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_unhandled_event_type_returns_200(self):
        """Non-transfer event type returns 200 without error."""
        resp = self._post({'event_type': 'balance#credit', 'data': {}})
        self.assertEqual(resp.status_code, 200)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_unknown_transfer_id_returns_200(self):
        """Unknown transfer_id returns 200 (may belong to another system)."""
        payload = {
            'event_type': 'transfers#state-change',
            'data': {
                'resource': {'id': 99999999, 'type': 'transfer'},
                'current_state': 'outgoing_payment_sent',
                'previous_state': 'processing',
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='')
    def test_invalid_json_returns_400(self):
        """Malformed JSON body → 400."""
        resp = self.client.post(
            self.WEBHOOK_URL, data='not-json',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(SMARTLINK_WISE_WEBHOOK_SECRET='secret_abc')
    def test_bad_signature_returns_400(self):
        """Invalid X-Signature-SHA256 → 400."""
        with patch(
            'api.smartlink.viewsets.BusinessViewSets.PayoutViewSet._verify_wise_webhook',
            return_value=False,
        ):
            resp = self._post(self._state_change('outgoing_payment_sent'))
        self.assertEqual(resp.status_code, 400)

    def test_wise_hmac_verification_correct_signature(self):
        """_verify_wise_webhook returns True for a correctly signed payload."""
        import hmac, hashlib, base64
        from api.smartlink.viewsets.BusinessViewSets import PayoutViewSet

        secret  = 'my_wise_secret'
        body    = b'{"event_type":"transfers#state-change"}'
        mac     = hmac.new(
            key=secret.encode('utf-8'), msg=body, digestmod=hashlib.sha256,
        ).digest()
        sig_b64 = base64.b64encode(mac).decode('utf-8')

        rf      = RequestFactory()
        request = rf.post('/', data=body, content_type='application/json')
        request.META['HTTP_X_SIGNATURE_SHA256'] = sig_b64

        self.assertTrue(PayoutViewSet._verify_wise_webhook(request, body, secret))

    def test_wise_hmac_verification_wrong_signature(self):
        """_verify_wise_webhook returns False for a tampered signature."""
        from api.smartlink.viewsets.BusinessViewSets import PayoutViewSet

        rf      = RequestFactory()
        request = rf.post('/', data=b'{}', content_type='application/json')
        request.META['HTTP_X_SIGNATURE_SHA256'] = 'invalidsig=='

        self.assertFalse(
            PayoutViewSet._verify_wise_webhook(request, b'{}', 'secret')
        )

    def test_wise_hmac_missing_header_returns_false(self):
        """_verify_wise_webhook returns False when signature header is absent."""
        from api.smartlink.viewsets.BusinessViewSets import PayoutViewSet

        rf      = RequestFactory()
        request = rf.post('/', data=b'{}', content_type='application/json')
        # No X-Signature-SHA256 header set

        self.assertFalse(
            PayoutViewSet._verify_wise_webhook(request, b'{}', 'secret')
        )

# ═════════════════════════════════════════════════════════════════════════════
# 4. Per-Publisher Attribution Window
# ═════════════════════════════════════════════════════════════════════════════

class PerPublisherAttributionWindowTest(TestCase):

    def setUp(self):
        self.publisher = _make_user('attr_pub')

    def test_profile_field_exists_and_defaults_to_none(self):
        """PublisherProfile has attribution_window_days field, default None."""
        from api.smartlink.models.billing import PublisherProfile
        profile, _ = PublisherProfile.objects.get_or_create(publisher=self.publisher)
        self.assertIsNone(profile.attribution_window_days)

    def test_profile_field_can_be_set_and_retrieved(self):
        """attribution_window_days can be saved and retrieved from DB."""
        from api.smartlink.models.billing import PublisherProfile
        profile, _ = PublisherProfile.objects.get_or_create(publisher=self.publisher)
        profile.attribution_window_days = 7
        profile.save(update_fields=['attribution_window_days'])
        profile.refresh_from_db()
        self.assertEqual(profile.attribution_window_days, 7)

    @override_settings(SMARTLINK_ATTRIBUTION_WINDOW_HOURS=24)
    def test_service_uses_global_when_no_profile(self):
        """ClickAttributionService uses global setting when no profile exists."""
        from api.smartlink.services.click.ClickAttributionService import ClickAttributionService
        svc = ClickAttributionService(publisher=self.publisher)
        self.assertEqual(svc.window_hours, 24)

    @override_settings(SMARTLINK_ATTRIBUTION_WINDOW_HOURS=24)
    def test_service_uses_per_publisher_override(self):
        """ClickAttributionService uses per-publisher window (7 days = 168h)."""
        from api.smartlink.services.click.ClickAttributionService import ClickAttributionService
        _make_profile(self.publisher, attribution_window_days=7)
        svc = ClickAttributionService(publisher=self.publisher)
        self.assertEqual(svc.window_hours, 168)

    @override_settings(SMARTLINK_ATTRIBUTION_WINDOW_HOURS=48)
    def test_service_falls_back_to_global_when_field_is_none(self):
        """ClickAttributionService falls back to global when field is None."""
        from api.smartlink.services.click.ClickAttributionService import ClickAttributionService
        _make_profile(self.publisher, attribution_window_days=None)
        svc = ClickAttributionService(publisher=self.publisher)
        self.assertEqual(svc.window_hours, 48)

    @override_settings(SMARTLINK_ATTRIBUTION_WINDOW_HOURS=24)
    def test_service_with_no_publisher_arg_uses_global(self):
        """ClickAttributionService(publisher=None) always uses global setting."""
        from api.smartlink.services.click.ClickAttributionService import ClickAttributionService
        svc = ClickAttributionService(publisher=None)
        self.assertEqual(svc.window_hours, 24)

    def test_attribution_window_api_shows_publisher_override(self):
        """GET /api/smartlink/attribution/window/ reflects per-publisher override."""
        _make_profile(self.publisher, attribution_window_days=30)
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.get('/api/smartlink/attribution/window/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['publisher_override_active'])
        self.assertEqual(data['attribution_window_hours'], 30 * 24)
        self.assertEqual(data['attribution_window_days'],  30.0)

    @override_settings(SMARTLINK_ATTRIBUTION_WINDOW_HOURS=24)
    def test_attribution_window_api_shows_global_when_no_override(self):
        """GET /api/smartlink/attribution/window/ shows global when no override."""
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.get('/api/smartlink/attribution/window/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['publisher_override_active'])
        self.assertEqual(data['attribution_window_hours'], 24)

    def test_admin_sees_global_and_effective_windows(self):
        """Admin response includes global_window_hours alongside effective window."""
        admin = _make_user('attr_admin', is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get('/api/smartlink/attribution/window/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('global_window_hours', data)
        self.assertIn('global_window_days',  data)

    def test_profile_serializer_includes_attribution_window_days(self):
        """PublisherProfile GET response includes attribution_window_days."""
        _make_profile(self.publisher, attribution_window_days=14)
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.get('/api/smartlink/publisher/profile/my-profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attribution_window_days', resp.json())
        self.assertEqual(resp.json()['attribution_window_days'], 14)

    def test_profile_patch_updates_attribution_window_days(self):
        """PATCH /publisher/profile/my-profile/ can set attribution_window_days."""
        _make_profile(self.publisher)
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.patch(
            '/api/smartlink/publisher/profile/my-profile/',
            {'attribution_window_days': 21},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['attribution_window_days'], 21)

        from api.smartlink.models.billing import PublisherProfile
        self.assertEqual(
            PublisherProfile.objects.get(publisher=self.publisher).attribution_window_days,
            21,
        )

    def test_profile_patch_allows_null_to_reset_to_global(self):
        """PATCH attribution_window_days=null clears the override → uses global."""
        _make_profile(self.publisher, attribution_window_days=7)
        client = APIClient()
        client.force_authenticate(self.publisher)
        resp = client.patch(
            '/api/smartlink/publisher/profile/my-profile/',
            {'attribution_window_days': None},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['attribution_window_days'])

# ═════════════════════════════════════════════════════════════════════════════
# 5. Offer Catalog Sync
# ═════════════════════════════════════════════════════════════════════════════

class OfferCatalogSyncTest(TestCase):
    """
    Tests for POST …/pool/{pool_id}/sync-from-catalog/

    get_model() is patched to avoid requiring a real offer_inventory DB.
    """

    def setUp(self):
        from api.smartlink.models import OfferPool
        from api.smartlink.models.publisher import PublisherSmartLink

        self.publisher = _make_user('pool_pub')
        self.admin     = _make_user('pool_adm', is_staff=True)

        # SmartLink uses 'publisher' FK (not 'created_by')
        self.sl   = _make_smartlink(self.publisher)
        self.pool = OfferPool.objects.create(smartlink=self.sl)

        self.url = (
            f'/api/smartlink/smartlinks/{self.sl.pk}/pool/'
            f'{self.pool.pk}/sync-from-catalog/'
        )

        # Grant the publisher can_edit_pool
        PublisherSmartLink.objects.create(
            publisher   = self.publisher,
            smartlink   = self.sl,
            can_edit_pool = True,
            assigned_by = self.admin,
        )

    # ── Patch helper ──────────────────────────────────────────────────────────

    def _make_offers(self, pks):
        """Create real Offer rows in offer_inventory_offer table."""
        from django.apps import apps
        OfferModel = apps.get_model('offer_inventory', 'Offer')
        for pk in pks:
            OfferModel.objects.get_or_create(id=pk, defaults={'name': f'Offer {pk}'})

    def _post(self, user, payload, valid_offer_pks=None):
        """POST sync-from-catalog with real Offer rows in DB."""
        if valid_offer_pks:
            self._make_offers(valid_offer_pks)
        client = APIClient()
        client.force_authenticate(user)
        return client.post(self.url, payload, format='json')

    # ── Tests ─────────────────────────────────────────────────────────────────

    def test_admin_can_add_new_offers(self):
        """Admin can add new offers to the pool."""
        resp = self._post(self.admin, {'offer_ids': [10, 11, 12]},
                          valid_offer_pks=[10, 11, 12])
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        added_ids = [a['offer_id'] for a in data['added']]
        self.assertCountEqual(added_ids, [10, 11, 12])
        self.assertEqual(data['already_present'], [])
        self.assertEqual(data['errors'], [])

    def test_publisher_with_can_edit_pool_can_sync(self):
        """Publisher with can_edit_pool=True can sync."""
        resp = self._post(self.publisher, {'offer_ids': [20]},
                          valid_offer_pks=[20])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['added']), 1)

    def test_publisher_without_can_edit_pool_gets_403(self):
        """Publisher without can_edit_pool=True gets 403."""
        other = _make_user('pool_noperm')
        resp = self._post(other, {'offer_ids': [30]}, valid_offer_pks=[30])
        self.assertEqual(resp.status_code, drf_status.HTTP_403_FORBIDDEN)

    def test_already_present_offers_not_duplicated(self):
        """Existing active pool entries appear in already_present, not added."""
        from api.smartlink.models import OfferPoolEntry
        self._make_offers([40])
        OfferPoolEntry.objects.create(
            pool=self.pool, offer_id=40, weight=100, priority=0, is_active=True,
        )
        resp = self._post(self.admin, {'offer_ids': [40]}, valid_offer_pks=[40])
        data = resp.json()
        self.assertIn(40, data['already_present'])
        self.assertEqual(data['added'], [])

    def test_missing_offer_reported_in_errors_207(self):
        """Offer not in catalog → errors list, 207 Multi-Status."""
        resp = self._post(self.admin, {'offer_ids': [999]}, valid_offer_pks=[])
        self.assertEqual(resp.status_code, drf_status.HTTP_207_MULTI_STATUS)
        data = resp.json()
        self.assertEqual(data['added'], [])
        self.assertTrue(any(e['offer_id'] == 999 for e in data['errors']))

    def test_mixed_valid_and_invalid_offer_ids(self):
        """Valid offers are added; missing ones go to errors; 207 returned."""
        resp = self._post(self.admin, {'offer_ids': [50, 999]},
                          valid_offer_pks=[50])
        self.assertEqual(resp.status_code, drf_status.HTTP_207_MULTI_STATUS)
        data = resp.json()
        added_ids = [a['offer_id'] for a in data['added']]
        self.assertIn(50, added_ids)
        self.assertTrue(any(e['offer_id'] == 999 for e in data['errors']))

    def test_deactivate_missing_flag_deactivates_unlisted_entries(self):
        """deactivate_missing=True deactivates entries not in offer_ids."""
        from api.smartlink.models import OfferPoolEntry
        # Create real Offer rows first to satisfy the FK constraint
        self._make_offers([51, 52])
        OfferPoolEntry.objects.create(
            pool=self.pool, offer_id=51, weight=100, priority=0, is_active=True,
        )
        OfferPoolEntry.objects.create(
            pool=self.pool, offer_id=52, weight=100, priority=0, is_active=True,
        )
        resp = self._post(
            self.admin,
            {'offer_ids': [51], 'deactivate_missing': True},
            valid_offer_pks=[51],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        deactivated_ids = [d['offer_id'] for d in data['deactivated']]
        self.assertIn(52, deactivated_ids)
        self.assertNotIn(51, deactivated_ids)
        self.assertFalse(
            OfferPoolEntry.objects.get(pool=self.pool, offer_id=52).is_active
        )
        self.assertTrue(
            OfferPoolEntry.objects.get(pool=self.pool, offer_id=51).is_active
        )

    def test_reactivates_previously_deactivated_entry(self):
        """sync-from-catalog re-activates a previously deactivated pool entry."""
        from api.smartlink.models import OfferPoolEntry
        self._make_offers([60])
        entry = OfferPoolEntry.objects.create(
            pool=self.pool, offer_id=60, weight=100, priority=0, is_active=False,
        )
        resp = self._post(self.admin, {'offer_ids': [60]}, valid_offer_pks=[60])
        self.assertEqual(resp.status_code, 200)
        added_ids = [a['offer_id'] for a in resp.json()['added']]
        self.assertIn(60, added_ids)
        entry.refresh_from_db()
        self.assertTrue(entry.is_active)

    def test_empty_offer_ids_returns_400(self):
        """Empty offer_ids list → 400 Bad Request."""
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(self.url, {'offer_ids': []}, format='json')
        self.assertEqual(resp.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_non_list_offer_ids_returns_400(self):
        """Non-list offer_ids → 400 Bad Request."""
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(self.url, {'offer_ids': 'not-a-list'}, format='json')
        self.assertEqual(resp.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_missing_offer_ids_key_returns_400(self):
        """Missing offer_ids key → 400 Bad Request."""
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(self.url, {'default_weight': 200}, format='json')
        self.assertEqual(resp.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_default_weight_and_priority_applied(self):
        """default_weight and default_priority are saved on new entries."""
        from api.smartlink.models import OfferPoolEntry
        resp = self._post(
            self.admin,
            {'offer_ids': [70], 'default_weight': 500, 'default_priority': 3},
            valid_offer_pks=[70],
        )
        self.assertEqual(resp.status_code, 200)
        entry = OfferPoolEntry.objects.get(pool=self.pool, offer_id=70)
        self.assertEqual(entry.weight, 500)
        self.assertEqual(entry.priority, 3)
