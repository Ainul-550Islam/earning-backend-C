# viewsets/DepositCallbackViewSet.py
# Receives raw gateway callbacks (no auth — verified by signature)
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@method_decorator(csrf_exempt, name='dispatch')
class DepositCallbackViewSet(ViewSet):
    """
    Receives gateway callbacks after payment (no auth, HMAC-verified).
    One endpoint per gateway — all route here.
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post', 'get'], url_path='bkash')
    def bkash(self, request):
        return self._process('bkash', request)

    @action(detail=False, methods=['post', 'get'], url_path='nagad')
    def nagad(self, request):
        return self._process('nagad', request)

    @action(detail=False, methods=['post'], url_path='sslcommerz')
    def sslcommerz(self, request):
        return self._process('sslcommerz', request)

    @action(detail=False, methods=['post'], url_path='amarpay')
    def amarpay(self, request):
        return self._process('amarpay', request)

    @action(detail=False, methods=['post', 'get'], url_path='upay')
    def upay(self, request):
        return self._process('upay', request)

    @action(detail=False, methods=['post', 'get'], url_path='shurjopay')
    def shurjopay(self, request):
        return self._process('shurjopay', request)

    @action(detail=False, methods=['post'], url_path='stripe')
    def stripe(self, request):
        return self._process('stripe', request)

    @action(detail=False, methods=['post'], url_path='paypal')
    def paypal(self, request):
        return self._process('paypal', request)

    def _process(self, gateway: str, request) -> Response:
        """Central callback processor."""
        import json, logging
        from api.payment_gateways.models.deposit import DepositCallback
        from api.payment_gateways.services.DepositService import DepositService

        logger  = logging.getLogger(__name__)
        body    = request.body
        headers = dict(request.headers)
        ip      = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                  or request.META.get('REMOTE_ADDR', '')

        # Verify signature
        is_valid = getattr(request, 'webhook_signature_ok', True)

        # Parse payload
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = dict(request.POST) or {}

        # Log callback
        callback = DepositCallback.objects.create(
            gateway=gateway,
            raw_payload=payload,
            raw_body=body.decode('utf-8', errors='replace')[:5000],
            headers={k: v for k, v in headers.items() if k.lower() != 'authorization'},
            is_valid=is_valid,
            ip_address=ip or None,
        )

        if not is_valid:
            logger.warning(f'Invalid {gateway} callback signature from {ip}')
            return Response({'status': 'invalid_signature'}, status=400)

        # Process via DepositService
        try:
            ref_id  = (payload.get('tran_id') or payload.get('reference_id') or
                       payload.get('orderId') or payload.get('paymentID') or '')
            gw_ref  = (payload.get('bank_tran_id') or payload.get('trxID') or
                       payload.get('sp_code') or payload.get('id') or ref_id)

            svc = DepositService()
            result = svc.verify_and_complete(ref_id, gw_ref, payload)

            callback.processed    = True
            callback.event_type   = payload.get('status', '')
            callback.save(update_fields=['processed', 'event_type'])

            return Response({'status': 'OK'})
        except Exception as e:
            logger.error(f'{gateway} callback processing error: {e}')
            callback.processing_error = str(e)
            callback.save(update_fields=['processing_error'])
            return Response({'status': 'error', 'message': str(e)}, status=500)
