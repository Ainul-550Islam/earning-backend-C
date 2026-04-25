# api/payment_gateways/webhooks/UpayWebhook.py

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import GatewayTransaction as TxnModel, PaymentGatewayWebhookLog


@csrf_exempt
@require_POST
def upay_callback(request):
    """
    Upay payment callback handler.
    Upay POSTs JSON to this endpoint after payment completion.
    """
    log = PaymentGatewayWebhookLog.objects.create(
        gateway='upay',
        payload={},
        headers=json.dumps(dict(request.headers)),
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    try:
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            payload = request.POST.dict()

        log.payload = payload
        log.save()

        order_id = (
            payload.get('merchant_order_id')
            or payload.get('order_id')
            or payload.get('tran_id')
        )
        pay_status = (
            payload.get('status')
            or payload.get('payment_status', '')
        )

        if order_id:
            try:
                txn = TxnModel.objects.get(reference_id=order_id)
                if str(pay_status).upper() in ('SUCCESS', 'SUCCESSFUL', 'COMPLETED'):
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
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        log.response = str(e)
        log.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
