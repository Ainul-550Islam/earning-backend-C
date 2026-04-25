# api/payment_gateways/webhooks/ShurjoPayWebhook.py

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import GatewayTransaction as TxnModel, PaymentGatewayWebhookLog


@csrf_exempt
def shurjopay_callback(request):
    """
    ShurjoPay return/cancel URL handler.
    ShurjoPay redirects GET/POST here after payment.
    """
    log = PaymentGatewayWebhookLog.objects.create(
        gateway='shurjopay',
        payload={},
        headers=json.dumps(dict(request.headers)),
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    try:
        if request.method == 'POST':
            try:
                payload = json.loads(request.body)
            except json.JSONDecodeError:
                payload = request.POST.dict()
        else:
            payload = request.GET.dict()

        log.payload = payload
        log.save()

        order_id = (
            payload.get('order_id')
            or payload.get('merchant_order_id')
        )
        sp_code = str(payload.get('sp_code', ''))

        if order_id:
            try:
                txn = TxnModel.objects.get(reference_id=order_id)
                if sp_code in ('1000', '1001'):
                    txn.status = 'completed'
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                else:
                    txn.status = 'failed'
                txn.metadata['callback_data'] = payload
                txn.save()
            except TxnModel.DoesNotExist:
                pass

        log.processed = True
        log.response  = 'OK'
        log.save()
        return JsonResponse({'status': 'ok', 'sp_code': sp_code})

    except Exception as e:
        log.response = str(e)
        log.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
