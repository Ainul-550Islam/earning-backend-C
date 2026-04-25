# api/payment_gateways/health_dashboard.py
# Real-time health dashboard
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import AllowAny,IsAdminUser
from rest_framework.response import Response
import logging
logger=logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def public_status(request):
    """Public status page — shows gateway availability."""
    from api.payment_gateways.models.core import PaymentGateway
    try:
        gateways=list(PaymentGateway.objects.filter(status='active').values('name','display_name','health_status','updated_at'))
        healthy=sum(1 for g in gateways if g['health_status']=='healthy')
        overall='operational' if healthy==len(gateways) else ('partial_outage' if healthy>0 else 'major_outage')
        return Response({'status':overall,'total':len(gateways),'healthy':healthy,'gateways':[{'name':g['display_name'],'status':g['health_status']} for g in gateways]})
    except Exception as e:
        return Response({'status':'unknown','error':str(e)})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_health(request):
    """Admin health dashboard with full metrics."""
    from api.payment_gateways.monitoring import PaymentMonitor
    from api.payment_gateways.integration_system.health_check import health_checker
    monitor=PaymentMonitor()
    return Response({'system_health':health_checker.run_all_checks(),'gateway_metrics':monitor.get_all_gateway_metrics(),'active_alerts':monitor.get_active_alerts(),'queue_depths':__import__('api.payment_gateways.integration_system.message_queue',fromlist=['message_queue']).message_queue.get_all_depths()})
