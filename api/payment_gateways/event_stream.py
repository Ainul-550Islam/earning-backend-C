# api/payment_gateways/event_stream.py
import json,time,logging
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
logger=logging.getLogger(__name__)

def sse_event_generator(user):
    import json as _json
    yield f"data: {_json.dumps({'type':'connected','user_id':user.id})}\n\n"
    last_txn_id=0
    for _ in range(120):  # max 10 min stream
        try:
            from api.payment_gateways.models.core import GatewayTransaction
            new_txns=GatewayTransaction.objects.filter(user=user,id__gt=last_txn_id,status='completed').order_by('id')
            for txn in new_txns[:10]:
                data={'type':'transaction','id':txn.id,'amount':float(txn.amount),'gateway':txn.gateway,'txn_type':txn.transaction_type}
                yield f"data: {_json.dumps(data)}\n\n"
                last_txn_id=txn.id
        except Exception as e:
            logger.debug(f'SSE error: {e}')
        yield f"data: {_json.dumps({'type':'ping','ts':int(time.time())})}\n\n"
        time.sleep(5)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_events_stream(request):
    """SSE endpoint for real-time payment events."""
    response=StreamingHttpResponse(sse_event_generator(request.user),content_type='text/event-stream')
    response['Cache-Control']='no-cache'
    response['X-Accel-Buffering']='no'
    return response
