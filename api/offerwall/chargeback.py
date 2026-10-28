"""
api/offerwall/chargeback.py

Chargeback & Reversal handler.

Providers (Tapjoy, AdGem, AdGate) send chargebacks when a conversion
is reversed post-approval.  This module:
  1. Receives the chargeback webhook payload
  2. Verifies signature
  3. Reverses the wallet credit
  4. Updates OfferConversion.status → 'chargeback'
  5. Notifies user
  6. Fires audit log

Endpoint:  POST /api/offerwall/webhooks/chargeback/
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────

class ChargebackService:
    """
    Handles the full chargeback lifecycle for a single conversion.

    Usage::

        result = ChargebackService.process(
            conversion_id='abc123',
            reason='fraudulent_activity',
            provider_reference='cb_ref_456',
            initiated_by='tapjoy',
        )
    """

    @staticmethod
    def process(conversion_id: str, reason: str = '',
                provider_reference: str = '', initiated_by: str = '') -> dict:
        """
        Idempotent chargeback processor.

        Returns dict with keys: success, error, conversion_id, reversed_amount
        """
        from api.offerwall.models import OfferConversion

        try:
            conv = OfferConversion.objects.select_related(
                'offer', 'offer__provider', 'user', 'transaction'
            ).get(conversion_id=conversion_id)
        except OfferConversion.DoesNotExist:
            logger.warning(f'[chargeback] conversion not found: {conversion_id}')
            return {'success': False, 'error': 'conversion_not_found'}

        if conv.status == 'chargeback':
            logger.info(f'[chargeback] already processed: {conversion_id}')
            return {'success': True, 'error': None,
                    'conversion_id': conversion_id, 'idempotent': True}

        if conv.status not in ('approved',):
            return {'success': False,
                    'error': f'cannot_chargeback_status_{conv.status}'}

        reversed_amount = conv.reward_amount + (conv.bonus_amount or Decimal('0'))

        with transaction.atomic():
            # 1 — reverse wallet credit
            wallet_reversed = ChargebackService._reverse_wallet(conv, reversed_amount)

            # 2 — update conversion
            conv.status           = 'chargeback'
            conv.rejection_reason = reason or 'Chargeback from provider'
            conv.notes            = (
                f'CB ref: {provider_reference} | initiated_by: {initiated_by}'
            )
            conv.save(update_fields=['status', 'rejection_reason', 'notes', 'updated_at'])

            # 3 — notify user
            ChargebackService._notify_user(conv, reversed_amount, reason)

            # 4 — audit
            ChargebackService._audit(conv, reversed_amount, reason,
                                     provider_reference, initiated_by)

        logger.info(f'[chargeback] processed: {conversion_id} | -{reversed_amount}')
        return {
            'success': True,
            'conversion_id': conversion_id,
            'reversed_amount': str(reversed_amount),
            'wallet_reversed': wallet_reversed,
        }

    @staticmethod
    def _reverse_wallet(conv, amount: Decimal) -> bool:
        try:
            from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
            result = OfferwallAdapterFactory.get('wallet').send({
                'user_id':       conv.user_id,
                'reward_amount': -amount,           # negative = debit
                'bonus_amount':  Decimal('0'),
                'conversion_id': f'cb_{conv.conversion_id}',
                'offer_title':   f'Chargeback: {conv.offer.title}',
                'offer_id':      str(conv.offer_id),
                'provider_type': conv.offer.provider.provider_type
                                 if conv.offer.provider else '',
            })
            return result.get('success', False)
        except Exception as e:
            logger.error(f'[chargeback] wallet reversal failed: {e}', exc_info=True)
            return False

    @staticmethod
    def _notify_user(conv, amount: Decimal, reason: str):
        try:
            from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
            OfferwallAdapterFactory.get('notification').send({
                'user_id':      conv.user_id,
                'event':        'reward_rejected',
                'offer_title':  conv.offer.title,
                'reward_amount': str(amount),
                'reward_currency': conv.reward_currency or 'Points',
                'conversion_id': conv.conversion_id,
                'reason':       reason or 'Chargeback from provider',
            })
        except Exception as e:
            logger.warning(f'[chargeback] notify failed: {e}')

    @staticmethod
    def _audit(conv, amount, reason, cb_ref, initiated_by):
        try:
            from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
            OfferwallAdapterFactory.get('audit').send({
                'user_id': conv.user_id,
                'action':  'OFFER_CHARGEBACK',
                'message': f'Chargeback processed: {conv.conversion_id}',
                'metadata': {
                    'conversion_id':      conv.conversion_id,
                    'reversed_amount':    str(amount),
                    'reason':             reason,
                    'provider_reference': cb_ref,
                    'initiated_by':       initiated_by,
                },
            })
        except Exception as e:
            logger.debug(f'[chargeback] audit failed: {e}')


# ─────────────────────────────────────────────────────────────
# Signature verification helper
# ─────────────────────────────────────────────────────────────

class ChargebackSignatureVerifier:
    """Verifies provider HMAC-SHA256 signatures on chargeback webhooks."""

    @staticmethod
    def verify(payload: bytes, signature: str, secret: str) -> bool:
        if not secret or not signature:
            return False
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.lower())


# ─────────────────────────────────────────────────────────────
# Webhook view
# ─────────────────────────────────────────────────────────────

class ChargebackWebhookView(APIView):
    """
    POST /api/offerwall/webhooks/chargeback/

    Generic chargeback endpoint.  Provider-specific views can subclass
    this and override `_get_secret()` and `_parse_payload()`.

    Expected JSON body::

        {
          "conversion_id":      "abc123",
          "provider_reference": "cb_ref_456",
          "reason":             "fraudulent_activity",
          "initiated_by":       "tapjoy",
          "signature":          "deadbeef..."
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        payload  = request.body
        sig      = request.headers.get('X-Signature', '')
        data     = request.data

        conversion_id      = data.get('conversion_id', '')
        provider_reference = data.get('provider_reference', '')
        reason             = data.get('reason', '')
        initiated_by       = data.get('initiated_by', '')

        if not conversion_id:
            return Response({'error': 'missing conversion_id'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Verify signature if provider secret available
        secret = self._get_secret(initiated_by)
        if secret:
            if not ChargebackSignatureVerifier.verify(payload, sig, secret):
                logger.warning(f'[chargeback] invalid signature from {initiated_by}')
                return Response({'error': 'invalid_signature'},
                                status=status.HTTP_401_UNAUTHORIZED)

        result = ChargebackService.process(
            conversion_id=conversion_id,
            reason=reason,
            provider_reference=provider_reference,
            initiated_by=initiated_by,
        )

        if result.get('success'):
            return Response({'status': 'ok', **result})

        http_status = status.HTTP_404_NOT_FOUND \
            if result.get('error') == 'conversion_not_found' \
            else status.HTTP_400_BAD_REQUEST
        return Response({'error': result.get('error')}, status=http_status)

    def _get_secret(self, provider_type: str) -> str:
        """
        Look up provider secret key from DB.
        FIX: Now supports all 5 providers (tapjoy, adgem, adgate, offertoro, persona).
        """
        if not provider_type:
            return ''
        try:
            from api.offerwall.models import OfferProvider
            prov = OfferProvider.objects.filter(
                provider_type=provider_type, status='active'
            ).first()
            return (prov.secret_key or '') if prov else ''
        except Exception:
            return ''


class AdGateChargebackView(ChargebackWebhookView):
    """
    FIX: AdGate chargebacks were unhandled — no provider-specific view.
    AdGate uses X-AdGate-Signature header.
    Endpoint: POST /api/offerwall/webhooks/chargeback/adgate/
    """

    def post(self, request):
        sig = request.headers.get('X-AdGate-Signature', '')
        if sig:
            request.META['HTTP_X_SIGNATURE'] = sig
        return super().post(request)

    def _get_secret(self, _):
        try:
            from api.offerwall.models import OfferProvider
            p = OfferProvider.objects.filter(
                provider_type='adgate', status='active').first()
            return (p.secret_key or '') if p else ''
        except Exception:
            return ''


class PersonaChargebackView(ChargebackWebhookView):
    """
    FIX: Persona chargebacks were unhandled.
    Persona sends MD5 hash in the body.
    Endpoint: POST /api/offerwall/webhooks/chargeback/persona/
    """

    def _get_secret(self, _):
        try:
            from api.offerwall.models import OfferProvider
            p = OfferProvider.objects.filter(
                provider_type='persona', status='active').first()
            return (p.secret_key or '') if p else ''
        except Exception:
            return ''


class TapjoyChargebackView(ChargebackWebhookView):
    """Tapjoy-specific chargeback — uses X-Tapjoy-Signature header."""

    def post(self, request):
        request.headers._store['x-signature'] = (
            'X-Signature',
            request.headers.get('X-Tapjoy-Signature', ''))
        return super().post(request)

    def _get_secret(self, _):
        try:
            from api.offerwall.models import OfferProvider
            p = OfferProvider.objects.filter(
                provider_type='tapjoy', status='active').first()
            return p.secret_key if p else ''
        except Exception:
            return ''
