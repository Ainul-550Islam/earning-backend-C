# kyc/transaction_monitoring/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .models import TransactionMonitoringRule, TransactionMonitoringAlert


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def tm_rules(request):
    """Admin — Transaction monitoring rules"""
    if request.method == 'GET':
        qs = TransactionMonitoringRule.objects.all().order_by('rule_type')
        return Response([{
            'id':               r.id,
            'name':             r.name,
            'rule_type':        r.rule_type,
            'is_active':        r.is_active,
            'threshold_amount': str(r.threshold_amount) if r.threshold_amount else None,
            'threshold_count':  r.threshold_count,
            'time_window_hours': r.time_window_hours,
            'action':           r.action,
            'severity':         r.severity,
        } for r in qs])

    # POST — create rule
    from django.utils import timezone
    rule = TransactionMonitoringRule.objects.create(
        name=request.data.get('name', ''),
        rule_type=request.data.get('rule_type', 'velocity'),
        is_active=request.data.get('is_active', True),
        threshold_amount=request.data.get('threshold_amount'),
        threshold_count=request.data.get('threshold_count'),
        time_window_hours=request.data.get('time_window_hours', 24),
        action=request.data.get('action', 'alert'),
        severity=request.data.get('severity', 'medium'),
        description=request.data.get('description', ''),
    )
    return Response({'id': rule.id, 'name': rule.name, 'message': 'Rule created'}, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def tm_rule_detail(request, rule_id):
    try:
        rule = TransactionMonitoringRule.objects.get(id=rule_id)
    except TransactionMonitoringRule.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    if request.method == 'DELETE':
        rule.delete(); return Response({'message': 'Rule deleted'})
    if 'is_active' in request.data: rule.is_active = request.data['is_active']
    if 'threshold_amount' in request.data: rule.threshold_amount = request.data['threshold_amount']
    if 'threshold_count'  in request.data: rule.threshold_count  = request.data['threshold_count']
    if 'action' in request.data: rule.action = request.data['action']
    rule.save()
    return Response({'id': rule.id, 'is_active': rule.is_active})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def tm_alerts(request):
    """Admin — Transaction monitoring alerts"""
    qs = TransactionMonitoringAlert.objects.select_related('user', 'rule').all().order_by('-created_at')
    status_f = request.query_params.get('status', 'open')
    if status_f: qs = qs.filter(status=status_f)
    limit = int(request.query_params.get('limit', 50))
    return Response([{
        'id':               a.id,
        'username':         a.user.username if a.user else None,
        'rule_name':        a.rule.name if a.rule else None,
        'status':           a.status,
        'total_amount':     str(a.total_amount) if a.total_amount else None,
        'transaction_count': a.transaction_count,
        'sar_filed':        a.sar_filed,
        'created_at':       a.created_at,
    } for a in qs[:limit]])


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def tm_alert_action(request, alert_id):
    """Resolve or escalate a TM alert"""
    from django.utils import timezone
    try:
        alert = TransactionMonitoringAlert.objects.get(id=alert_id)
    except TransactionMonitoringAlert.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    action = request.data.get('action', 'close')
    if action == 'escalate':
        alert.status    = 'escalated'
        alert.sar_filed = True
    else:
        alert.status = 'closed'
    alert.resolution_note = request.data.get('note', '')
    alert.resolved_at = timezone.now()
    alert.save()
    return Response({'message': f'Alert {action}d', 'status': alert.status})
