# api/payment_gateways/status_page.py
# Public status page
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone

@api_view(['GET'])
@permission_classes([AllowAny])
def status_page(request):
    """Full public status page for payment_gateways."""
    from api.payment_gateways.models.core import PaymentGateway
    from django.core.cache import cache
    cached=cache.get('pg:public:status')
    if cached: return Response(cached)
    try:
        gateways=[]
        for gw in PaymentGateway.objects.filter(status='active').order_by('sort_order'):
            gateways.append({'name':gw.name,'display_name':gw.display_name,'status':gw.health_status,'region':gw.region,'supports_deposit':gw.supports_deposit,'supports_withdrawal':gw.supports_withdrawal})
        healthy=sum(1 for g in gateways if g['status']=='healthy')
        degraded=sum(1 for g in gateways if g['status']=='degraded')
        down=sum(1 for g in gateways if g['status']=='down')
        if down>0: overall_status='partial_outage' if healthy>0 else 'major_outage'
        elif degraded>0: overall_status='degraded'
        else: overall_status='operational'
        data={'status':overall_status,'timestamp':timezone.now().isoformat(),'gateways':gateways,'summary':{'total':len(gateways),'healthy':healthy,'degraded':degraded,'down':down},'version':'2.0.0'}
        cache.set('pg:public:status',data,60)
        return Response(data)
    except Exception as e:
        return Response({'status':'unknown','error':str(e),'timestamp':timezone.now().isoformat()})
