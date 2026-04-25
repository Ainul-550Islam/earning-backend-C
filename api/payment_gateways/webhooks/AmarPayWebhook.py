# api/payment_gateways/webhooks/AmarPayWebhook.py

import json
import hashlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from ..models import GatewayTransaction as TxnModel, PaymentGatewayWebhookLog


@csrf_exempt
@require_POST
def amarpay_ipn(request):
    """
    AmarPay IPN / callback handler.
    AmarPay POSTs JSON or form data to this endpoint.
    """
    log = PaymentGatewayWebhookLog.objects.create(
        gateway='amarpay',
        payload=request.POST.dict() or {},
        headers=json.dumps(dict(request.headers)),
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    try:
        ipn_data   = request.POST.dict()
        mer_txnid  = ipn_data.get('mer_txnid') or ipn_data.get('tran_id')
        pay_status = ipn_data.get('pay_status', '')

        if mer_txnid:
            try:
                txn = TxnModel.objects.get(reference_id=mer_txnid)
                if pay_status == 'Successful':
                    txn.status = 'completed'
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                else:
                    txn.status = 'failed'
                txn.metadata['ipn_data'] = ipn_data
                txn.save()
            except TxnModel.DoesNotExist:
                pass

        log.processed = True
        log.response  = 'OK'
        log.save()
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        log.response = str(e)
        log.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
