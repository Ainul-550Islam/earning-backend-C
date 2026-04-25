# api/payment_gateways/endpoint.py
# Custom DRF endpoint helpers for payment_gateways

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page


@api_view(['GET'])
@permission_classes([AllowAny])
def gateway_status_endpoint(request):
    """Public gateway status endpoint."""
    from api.payment_gateways.integration_system.health_check import health_checker
    status = health_checker.run_all_checks()
    code   = 200 if status['status'] == 'healthy' else 206
    return Response({'status': status['status'], 'gateways': status['checks'].get('gateways', {})}, status=code)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_deposit_endpoint(request):
    """Direct deposit initiation endpoint."""
    from decimal import Decimal
    from api.payment_gateways.services.DepositService import DepositService
    from api.payment_gateways.services.PaymentValidator import PaymentValidator

    data    = request.data
    gateway = data.get('gateway', 'bkash')
    amount  = Decimal(str(data.get('amount', '0')))
    currency= data.get('currency', 'BDT')

    validator = PaymentValidator()
    is_valid, errors = validator.validate_deposit(request.user, amount, gateway, currency)
    if not is_valid:
        return Response({'success': False, 'errors': errors}, status=400)

    try:
        svc    = DepositService()
        result = svc.initiate(request.user, amount, gateway, currency,
                               ip=request.META.get('REMOTE_ADDR'),
                               user_agent=request.META.get('HTTP_USER_AGENT', ''))
        return Response({'success': True, 'data': result})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_earnings_summary_endpoint(request):
    """Quick earnings summary for publisher."""
    from django.db.models import Sum, Count
    from api.payment_gateways.tracking.models import Conversion
    from django.utils import timezone

    today = timezone.now().date()
    qs    = Conversion.objects.filter(publisher=request.user, status='approved')

    return Response({'success': True, 'data': {
        'today':   float(qs.filter(created_at__date=today).aggregate(t=Sum('payout'))['t'] or 0),
        'balance': float(getattr(request.user, 'balance', 0) or 0),
        'all_time':float(qs.aggregate(t=Sum('payout'))['t'] or 0),
    }})
