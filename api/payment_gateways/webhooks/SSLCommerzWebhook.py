# api/payment_gateways/webhooks/SSLCommerzWebhook.py

import json
import hashlib
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from ..models import GatewayTransaction as TxnModel, PaymentGatewayWebhookLog


@csrf_exempt
@require_POST
def sslcommerz_ipn(request):
    """
    SSLCommerz IPN (Instant Payment Notification) handler.
    SSLCommerz POSTs form data to this endpoint.
    """
    log = PaymentGatewayWebhookLog.objects.create(
        gateway='sslcommerz',
        payload=request.POST.dict(),
        headers=json.dumps(dict(request.headers)),
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    try:
        ipn_data = request.POST.dict()

        # Verify IPN signature
        verify_sign = ipn_data.get('verify_sign')
        verify_key  = ipn_data.get('verify_key')
        store_passwd = getattr(settings, 'SSLCOMMERZ_STORE_PASSWORD', '')

        if not _verify_ipn_hash(ipn_data, verify_sign, verify_key, store_passwd):
            log.response = 'INVALID_SIGNATURE'
            log.save()
            return HttpResponse('INVALID', status=400)

        tran_id = ipn_data.get('tran_id')
        status  = ipn_data.get('status')

        try:
            txn = TxnModel.objects.get(reference_id=tran_id)
            if status == 'VALID' or status == 'VALIDATED':
                txn.status = 'completed'
                user = txn.user
                if hasattr(user, 'balance'):
                    user.balance += txn.net_amount
                    user.save(update_fields=['balance'])
            elif status in ('FAILED', 'CANCELLED', 'UNATTEMPTED', 'EXPIRED'):
                txn.status = 'failed'
            txn.metadata['ipn_data'] = ipn_data
            txn.save()
        except TxnModel.DoesNotExist:
            pass

        log.processed = True
        log.response  = 'OK'
        log.save()
        return HttpResponse('OK')

    except Exception as e:
        log.response = str(e)
        log.save()
        return HttpResponse('ERROR', status=500)


def _verify_ipn_hash(ipn_data, verify_sign, verify_key, store_passwd):
    """Verify SSLCommerz IPN hash"""
    if not verify_sign or not verify_key:
        return False
    keys = verify_key.split(',')
    hash_string = store_passwd
    for key in sorted(keys):
        hash_string += ipn_data.get(key, '')
    generated = hashlib.md5(hash_string.encode()).hexdigest()
    return generated == verify_sign
