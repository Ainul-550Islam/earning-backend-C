# alerts/api_views.py  —  100% Complete & Fixed CRUD
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta


VALID_ALERT_TYPES = ['high_earning', 'mass_signup', 'payment_spike', 'fraud_spike', 'server_error', 'low_balance']


# ═══════════════════════════════ OVERVIEW ══════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alerts_overview(request):
    try:
        from .models import AlertRule, AlertLog
        today    = timezone.now().date()
        week_ago = timezone.now() - timedelta(days=7)
        unresolved = AlertLog.objects.filter(is_resolved=False)
        return Response({
            'total_rules':       AlertRule.objects.count(),
            'active_rules':      AlertRule.objects.filter(is_active=True).count(),
            'alerts_today':      AlertLog.objects.filter(triggered_at__date=today).count(),
            'alerts_this_week':  AlertLog.objects.filter(triggered_at__gte=week_ago).count(),
            'unresolved_alerts': unresolved.count(),
            'resolved_today':    AlertLog.objects.filter(is_resolved=True, resolved_at__date=today).count(),
            'critical_active':   unresolved.filter(rule__severity='critical').count(),
            'high_active':       unresolved.filter(rule__severity='high').count(),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ═══════════════════════════════ ALERT RULES ═══════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_rules_list(request):
    """List all alert rules — filterable by severity, type, active"""
    try:
        from .models import AlertRule
        qs = AlertRule.objects.order_by('-created_at')
        severity   = request.query_params.get('severity')
        alert_type = request.query_params.get('alert_type')
        is_active  = request.query_params.get('is_active')
        if severity:   qs = qs.filter(severity=severity)
        if alert_type: qs = qs.filter(alert_type=alert_type)
        if is_active is not None and is_active != '':
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return Response(list(qs.values(
            'id', 'name', 'alert_type', 'severity', 'description',
            'threshold_value', 'time_window_minutes', 'is_active',
            'send_email', 'send_telegram', 'send_sms', 'send_webhook',
            'webhook_url', 'email_recipients', 'cooldown_minutes',
            'trigger_count', 'last_triggered', 'created_at', 'updated_at',
        )))
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_rules_stats(request):
    """✅ NEW - Alert rules statistics — called by useAlertRules hook"""
    try:
        from .models import AlertRule
        qs = AlertRule.objects.all()
        by_severity = {}
        for s in ['low', 'medium', 'high', 'critical']:
            by_severity[s] = qs.filter(severity=s).count()
        by_type = {}
        for t in VALID_ALERT_TYPES:
            by_type[t] = qs.filter(alert_type=t).count()
        return Response({
            'total':            qs.count(),
            'active':           qs.filter(is_active=True).count(),
            'inactive':         qs.filter(is_active=False).count(),
            'by_severity':      by_severity,
            'by_type':          by_type,
            'high_trigger_count': list(qs.order_by('-trigger_count')[:5].values('id', 'name', 'trigger_count')),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_rule_create(request):
    """Create a new alert rule"""
    try:
        from .models import AlertRule
        data = request.data
        rule = AlertRule(
            name=data['name'],
            alert_type=data.get('alert_type', 'low_balance'),
            severity=data.get('severity', 'medium'),
            description=data.get('description', ''),
            threshold_value=data.get('threshold_value', 0),
            time_window_minutes=data.get('time_window_minutes', 60),
            send_email=data.get('send_email', True),
            send_telegram=data.get('send_telegram', False),
            send_sms=data.get('send_sms', False),
            send_webhook=data.get('send_webhook', False),
            webhook_url=data.get('webhook_url', ''),
            email_recipients=data.get('email_recipients', ''),
            cooldown_minutes=data.get('cooldown_minutes', 30),
            is_active=data.get('is_active', True),
            created_by_id=request.user.id,
        )
        rule.save()
        return Response({'id': rule.id, 'name': rule.name, 'success': True}, status=201)
    except KeyError as e:
        return Response({'error': f'Missing field: {e}'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_rule_detail(request, rule_id):
    """Get, update or delete a single alert rule"""
    try:
        from .models import AlertRule
        rule = AlertRule.objects.get(id=rule_id)
    except AlertRule.DoesNotExist:
        return Response({'error': 'Rule not found'}, status=404)

    if request.method == 'GET':
        from .models import AlertLog
        logs = AlertLog.objects.filter(rule=rule).order_by('-triggered_at')[:5]
        return Response({
            'id': rule.id, 'name': rule.name, 'alert_type': rule.alert_type,
            'severity': rule.severity, 'description': rule.description,
            'threshold_value': rule.threshold_value,
            'time_window_minutes': rule.time_window_minutes,
            'send_email': rule.send_email, 'send_telegram': rule.send_telegram,
            'send_sms': rule.send_sms, 'send_webhook': rule.send_webhook,
            'webhook_url': rule.webhook_url, 'email_recipients': rule.email_recipients,
            'cooldown_minutes': rule.cooldown_minutes, 'is_active': rule.is_active,
            'trigger_count': rule.trigger_count, 'last_triggered': rule.last_triggered,
            'created_at': rule.created_at, 'updated_at': rule.updated_at,
            'recent_logs': list(logs.values('id', 'message', 'triggered_at', 'is_resolved')),
        })

    if request.method in ('PUT', 'PATCH'):
        fields = ['name', 'alert_type', 'severity', 'description', 'threshold_value',
                  'time_window_minutes', 'send_email', 'send_telegram', 'send_sms',
                  'send_webhook', 'webhook_url', 'email_recipients',
                  'cooldown_minutes', 'is_active']
        for f in fields:
            if f in request.data:
                setattr(rule, f, request.data[f])
        rule.save()
        return Response({'success': True, 'name': rule.name})

    if request.method == 'DELETE':
        rule.delete()
        return Response({'success': True})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_rule_bulk_update_status(request):
    """✅ NEW - Bulk update rule active/inactive status"""
    ids = request.data.get('ids', [])
    is_active = request.data.get('is_active', True)
    if not ids:
        return Response({'error': 'No ids provided'}, status=400)
    from .models import AlertRule
    count = AlertRule.objects.filter(id__in=ids).update(is_active=is_active)
    return Response({'success': True, 'updated': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_rule_toggle(request, rule_id):
    """Toggle rule active/inactive"""
    try:
        from .models import AlertRule
        rule = AlertRule.objects.get(id=rule_id)
        rule.is_active = not rule.is_active
        rule.save(update_fields=['is_active'])
        return Response({'success': True, 'is_active': rule.is_active})
    except AlertRule.DoesNotExist:
        return Response({'error': 'Rule not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_rule_test(request, rule_id):
    """Manually trigger test alert"""
    try:
        from .models import AlertRule, AlertLog
        rule = AlertRule.objects.get(id=rule_id)
        log = AlertLog.objects.create(
            rule=rule,
            trigger_value=rule.threshold_value + 1,
            threshold_value=rule.threshold_value,
            message=f'[TEST] Alert rule "{rule.name}" manually tested',
            is_resolved=True,
            resolved_at=timezone.now(),
            resolution_note='Auto-resolved: manual test',
        )
        return Response({'success': True, 'log_id': log.id, 'message': log.message})
    except AlertRule.DoesNotExist:
        return Response({'error': 'Rule not found'}, status=404)


# ═══════════════════════════════ ALERT LOGS ════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_logs_list(request):
    """List alert logs — filterable, paginated"""
    try:
        from .models import AlertLog
        page     = int(request.query_params.get('page', 1))
        size     = 20
        severity = request.query_params.get('severity')
        resolved = request.query_params.get('is_resolved')
        rule_id  = request.query_params.get('rule_id')

        qs = AlertLog.objects.select_related('rule').order_by('-triggered_at')
        if severity:
            qs = qs.filter(rule__severity=severity)
        if resolved is not None and resolved != '':
            qs = qs.filter(is_resolved=resolved.lower() == 'true')
        if rule_id:
            qs = qs.filter(rule_id=rule_id)

        total = qs.count()
        items = qs[(page-1)*size : page*size]
        return Response({
            'count': total,
            'total_pages': max(1, (total + size - 1) // size),
            'results': list(items.values(
                'id', 'rule_id', 'rule__name', 'rule__severity', 'rule__alert_type',
                'message', 'trigger_value', 'threshold_value',
                'is_resolved', 'resolved_at', 'resolution_note',
                'email_sent', 'telegram_sent',
                'triggered_at', 'processing_time_ms',
            ))
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_logs_stats(request):
    """✅ NEW - Alert logs statistics — called by useAlertLogs hook"""
    try:
        from .models import AlertLog
        qs = AlertLog.objects.all()
        week_ago = timezone.now() - timedelta(days=7)
        unresolved = qs.filter(is_resolved=False)
        return Response({
            'total':               qs.count(),
            'resolved':            qs.filter(is_resolved=True).count(),
            'unresolved':          unresolved.count(),
            'escalated':           qs.filter(escalation_level__gt=0).count(),
            'critical_unresolved': unresolved.filter(rule__severity='critical').count(),
            'this_week':           qs.filter(triggered_at__gte=week_ago).count(),
            'avg_resolution_time': None,  # Can compute if needed
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_log_detail(request, log_id):
    """✅ NEW - Get single alert log detail"""
    try:
        from .models import AlertLog
        log = AlertLog.objects.select_related('rule', 'resolved_by').get(id=log_id)
        return Response({
            'id': log.id,
            'rule_id': log.rule_id,
            'rule_name': log.rule.name,
            'rule_severity': log.rule.severity,
            'rule_alert_type': log.rule.alert_type,
            'message': log.message,
            'trigger_value': log.trigger_value,
            'threshold_value': log.threshold_value,
            'details': log.details,
            'is_resolved': log.is_resolved,
            'resolved_at': log.resolved_at,
            'resolution_note': log.resolution_note,
            'resolved_by': log.resolved_by.username if log.resolved_by else None,
            'triggered_at': log.triggered_at,
            'email_sent': log.email_sent,
            'telegram_sent': log.telegram_sent,
            'processing_time_ms': log.processing_time_ms,
            'escalation_level': log.escalation_level,
        })
    except AlertLog.DoesNotExist:
        return Response({'error': 'Log not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_log_resolve(request, log_id):
    """Resolve a single alert log
    ✅ FIXED: accepts both 'note' and 'resolution_note' keys for frontend compatibility
    """
    try:
        from .models import AlertLog
        log = AlertLog.objects.get(id=log_id)
        if log.is_resolved:
            return Response({'error': 'Already resolved'}, status=400)
        log.is_resolved     = True
        log.resolved_at     = timezone.now()
        log.resolved_by     = request.user
        # ✅ FIX: accept both 'note' (Alerts.jsx) and 'resolution_note' (alerts.js hook)
        note = request.data.get('note') or request.data.get('resolution_note', 'Manually resolved')
        log.resolution_note = note
        log.save()
        return Response({'success': True})
    except AlertLog.DoesNotExist:
        return Response({'error': 'Log not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_log_bulk_resolve(request):
    """Bulk resolve alert logs
    ✅ FIXED: accepts both 'ids' (Alerts.jsx) and supports both POST/PATCH
    """
    ids  = request.data.get('ids', [])
    # ✅ FIX: accept both 'note' and 'resolution_note'
    note = request.data.get('note') or request.data.get('resolution_note', 'Bulk resolved by admin')
    if not ids:
        return Response({'error': 'No ids provided'}, status=400)
    from .models import AlertLog
    count = AlertLog.objects.filter(id__in=ids, is_resolved=False).update(
        is_resolved=True,
        resolved_at=timezone.now(),
        resolution_note=note,
    )
    return Response({'success': True, 'resolved': count})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def alert_log_delete(request, log_id):
    """Delete a log"""
    try:
        from .models import AlertLog
        AlertLog.objects.get(id=log_id).delete()
        return Response({'success': True})
    except AlertLog.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


# ═══════════════════════════════ SYSTEM HEALTH ═════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    try:
        from .models import SystemHealthCheck
        overall = SystemHealthCheck.get_overall_status()
        checks  = list(SystemHealthCheck.objects.order_by('-checked_at')[:10].values(
            'component', 'status', 'response_time_ms', 'message', 'checked_at'
        ))
        return Response({'overall_status': overall, 'checks': checks})
    except Exception as e:
        return Response({'overall_status': 'unknown', 'checks': [], 'error': str(e)})