# kyc/aml/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .models import PEPSanctionsScreening, AMLAlert
from .screening_service import AMLScreeningService


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def run_aml_screening(request, kyc_id):
    """Admin — Run AML/PEP/Sanctions screening on a KYC"""
    from kyc.models import KYC
    try:
        kyc = KYC.objects.get(id=kyc_id)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)

    provider = request.data.get('provider', 'mock')
    service  = AMLScreeningService(provider=provider)
    result   = service.screen(kyc)
    screening = service.save_result(kyc, result)

    return Response({
        'kyc_id':   kyc_id,
        'screening_id': screening.id,
        **result.to_dict(),
        'matches': result.matches,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def aml_screening_history(request, kyc_id):
    """AML screening history for a KYC"""
    screenings = PEPSanctionsScreening.objects.filter(kyc_id=kyc_id).order_by('-screened_at')
    data = [{
        'id':            s.id,
        'provider':      s.provider,
        'status':        s.status,
        'is_pep':        s.is_pep,
        'is_sanctioned': s.is_sanctioned,
        'match_count':   s.match_count,
        'match_score':   s.match_score,
        'screened_at':   s.screened_at,
    } for s in screenings]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def aml_alerts_list(request):
    """All open AML alerts"""
    status_filter = request.query_params.get('status', 'open')
    alerts = AMLAlert.objects.filter(status=status_filter).select_related('user', 'kyc').order_by('-created_at')
    tenant = getattr(request.user, 'tenant', None)
    if tenant: alerts = alerts.filter(tenant=tenant)
    data = [{
        'id':          a.id,
        'alert_type':  a.alert_type,
        'severity':    a.severity,
        'status':      a.status,
        'username':    a.user.username,
        'description': a.description,
        'sar_filed':   a.sar_filed,
        'created_at':  a.created_at,
    } for a in alerts]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def aml_resolve_alert(request, alert_id):
    """Resolve an AML alert"""
    try:
        alert = AMLAlert.objects.get(id=alert_id)
    except AMLAlert.DoesNotExist:
        return Response({'error': 'Alert not found'}, status=404)
    from django.utils import timezone
    action = request.data.get('action', 'close')   # 'close' | 'escalate'
    note   = request.data.get('note', '')
    if action == 'escalate':
        alert.status     = 'escalated'
        alert.sar_filed  = True
        alert.sar_reference = request.data.get('sar_reference', '')
    else:
        alert.status = 'closed'
    alert.resolved_by   = request.user
    alert.resolution_note = note
    alert.resolved_at   = timezone.now()
    alert.save()
    return Response({'message': f'Alert {action}d', 'status': alert.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def aml_false_positive(request, screening_id):
    """Mark AML screening as false positive"""
    try:
        s = PEPSanctionsScreening.objects.get(id=screening_id)
    except PEPSanctionsScreening.DoesNotExist:
        return Response({'error': 'Screening not found'}, status=404)
    s.mark_false_positive(reviewer=request.user, note=request.data.get('note',''))
    return Response({'message': 'Marked as false positive', 'status': s.status})
