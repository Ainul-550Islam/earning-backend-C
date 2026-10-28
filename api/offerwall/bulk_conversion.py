"""
api/offerwall/bulk_conversion.py

Bulk conversion webhook — providers POST multiple conversions in one request.

Supported:  AdGate, Tapjoy (bulk mode), custom providers
Endpoint:   POST /api/offerwall/webhooks/bulk/

Body::
    {
      "provider":     "adgate",
      "signature":    "...",
      "conversions": [
        {
          "user_id":        "42",
          "offer_id":       "EXT-001",
          "transaction_id": "TXN-A",
          "payout":         "0.70",
          "currency":       "USD",
          "status":         "approved"
        },
        ...
      ]
    }

Response::
    {
      "received":   10,
      "processed":  9,
      "duplicates": 1,
      "errors":     0,
      "results":    [ { "transaction_id": "TXN-A", "status": "created" }, ... ]
    }
"""
import hashlib
import hmac
import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)
User   = get_user_model()

MAX_BULK_SIZE = 500   # safety cap per request


# ─────────────────────────────────────────────────────────────
# Processing helpers
# ─────────────────────────────────────────────────────────────

class BulkConversionProcessor:

    def __init__(self, provider_obj):
        self.provider = provider_obj

    def process_batch(self, conversions: list) -> dict:
        """
        Process a list of raw conversion dicts.
        Each item must have: user_id, offer_id (external), transaction_id, payout, status.
        """
        results   = []
        processed = duplicates = errors = 0

        for item in conversions[:MAX_BULK_SIZE]:
            result = self._process_one(item)
            results.append(result)
            if result['status'] == 'created':
                processed += 1
            elif result['status'] == 'duplicate':
                duplicates += 1
            else:
                errors += 1

        return {
            'received':   len(conversions),
            'processed':  processed,
            'duplicates': duplicates,
            'errors':     errors,
            'results':    results,
        }

    @transaction.atomic
    def _process_one(self, item: dict) -> dict:
        tx_id = item.get('transaction_id', '')

        from api.offerwall.models import OfferConversion, Offer
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService as OIS)

        # Idempotency — skip duplicates
        if OfferConversion.objects.filter(
                external_WalletTransaction_id=tx_id).exists():
            return {'transaction_id': tx_id, 'status': 'duplicate'}

        try:
            # Resolve user
            raw_uid = item.get('user_id', '')
            try:
                user = User.objects.get(id=int(raw_uid))
            except (User.DoesNotExist, ValueError, TypeError):
                return {'transaction_id': tx_id, 'status': 'error',
                        'error': f'user_not_found:{raw_uid}'}

            # Resolve offer
            ext_offer_id = str(item.get('offer_id', ''))
            try:
                offer = Offer.objects.get(
                    provider=self.provider,
                    external_offer_id=ext_offer_id,
                )
            except Offer.DoesNotExist:
                return {'transaction_id': tx_id, 'status': 'error',
                        'error': f'offer_not_found:{ext_offer_id}'}

            payout = Decimal(str(item.get('payout', '0')))
            reward = payout * (self.provider.revenue_share / Decimal('100'))

            result = OIS.process_conversion(
                offer=offer,
                user=user,
                payout_amount=payout,
                reward_amount=reward,
                external_tx_id=tx_id,
                provider_data=item,
                auto_approve=(str(item.get('status', 'pending')) == 'approved'),
            )

            return {
                'transaction_id': tx_id,
                'status':         'created' if result.get('success') else 'error',
                'conversion_id':  result.get('conversion_id'),
                'error':          result.get('error'),
            }

        except IntegrityError:
            return {'transaction_id': tx_id, 'status': 'duplicate'}
        except Exception as e:
            logger.exception(f'[bulk] error processing {tx_id}: {e}')
            return {'transaction_id': tx_id, 'status': 'error', 'error': str(e)}


# ─────────────────────────────────────────────────────────────
# Signature verification
# ─────────────────────────────────────────────────────────────

def verify_bulk_signature(payload: bytes, sig: str, secret: str) -> bool:
    if not secret:
        return True   # signature check optional if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


# ─────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────

class BulkConversionWebhookView(APIView):
    """
    POST /api/offerwall/webhooks/bulk/

    Accepts batch conversions from providers.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        payload  = request.body
        sig      = request.headers.get('X-Signature', '')
        data     = request.data

        provider_type = data.get('provider', '')
        conversions   = data.get('conversions', [])

        if not isinstance(conversions, list):
            return Response({'error': 'conversions must be a list'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not conversions:
            return Response({'error': 'empty conversions list'},
                            status=status.HTTP_400_BAD_REQUEST)

        if len(conversions) > MAX_BULK_SIZE:
            return Response(
                {'error': f'batch too large (max {MAX_BULK_SIZE})'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        # Resolve provider
        from api.offerwall.models import OfferProvider
        try:
            provider = OfferProvider.objects.get(
                provider_type=provider_type, status='active')
        except OfferProvider.DoesNotExist:
            return Response({'error': 'unknown_provider'},
                            status=status.HTTP_404_NOT_FOUND)

        # Verify signature
        if not verify_bulk_signature(payload, sig, provider.secret_key or ''):
            logger.warning(f'[bulk] invalid sig from {provider_type}')
            return Response({'error': 'invalid_signature'},
                            status=status.HTTP_401_UNAUTHORIZED)

        processor = BulkConversionProcessor(provider)
        results   = processor.process_batch(conversions)

        logger.info(
            f'[bulk] {provider_type} | received={results["received"]} '
            f'processed={results["processed"]} dup={results["duplicates"]} '
            f'err={results["errors"]}'
        )

        return Response(results, status=status.HTTP_200_OK)
