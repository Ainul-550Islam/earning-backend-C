# kyc/api/v2/views.py  ── WORLD #1
"""API v2 — World #1 enhanced endpoints"""
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def v2_kyc_status(request):
    """v2 — Rich status with risk profile, steps, notifications"""
    from ...models import KYCSubmission, KYC, KYCVerificationStep
    from ...serializers import KYCSubmissionSerializer

    submission = KYCSubmission.objects.filter(user=request.user).order_by('-submitted_at', '-created_at').first()
    kyc        = KYC.objects.filter(user=request.user).first()

    base = {
        'status':                'not_submitted',
        'verification_progress': 0,
        'document_type':         None,
        'risk_score':            0,
        'risk_level':            'low',
        'steps':                 [],
        'notifications_unread':  0,
    }

    if submission:
        base.update(KYCSubmissionSerializer(submission, context={'request': request}).data)

    if kyc:
        base['risk_score'] = kyc.risk_score
        from ...utils.risk_utils import risk_level_from_score
        base['risk_level'] = risk_level_from_score(kyc.risk_score)
        steps = KYCVerificationStep.objects.filter(kyc=kyc).order_by('order')
        base['steps'] = [{'step': s.step, 'status': s.status, 'order': s.order} for s in steps]

    from ...models import KYCNotificationLog
    base['notifications_unread'] = KYCNotificationLog.objects.filter(
        user=request.user, is_read=False
    ).count()

    return Response(base)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def v2_kyc_admin_dashboard(request):
    """v2 Admin — Comprehensive dashboard with charts data"""
    from ...models import KYC, KYCAnalyticsSnapshot
    from django.db.models import Count, Avg

    qs = KYC.objects.all()

    # Last 7 days trend
    import datetime
    today = timezone.now().date()
    trend = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        trend.append({
            'date':      d.strftime('%Y-%m-%d'),
            'submitted': qs.filter(created_at__date=d).count(),
            'verified':  qs.filter(reviewed_at__date=d, status='verified').count(),
            'rejected':  qs.filter(reviewed_at__date=d, status='rejected').count(),
        })

    return Response({
        'summary': {
            'total':            qs.count(),
            'verified':         qs.filter(status='verified').count(),
            'pending':          qs.filter(status='pending').count(),
            'rejected':         qs.filter(status='rejected').count(),
            'high_risk':        qs.filter(risk_score__gt=60).count(),
            'duplicates':       qs.filter(is_duplicate=True).count(),
            'avg_risk_score':   round(qs.aggregate(avg=Avg('risk_score'))['avg'] or 0, 2),
            'submitted_today':  qs.filter(created_at__date=today).count(),
        },
        'trend_7d':     trend,
        'by_doc_type':  list(qs.values('document_type').annotate(count=Count('id')).order_by('-count')),
        'by_status':    list(qs.values('status').annotate(count=Count('id')).order_by('-count')),
        'by_risk_level': [
            {'level': 'low',      'count': qs.filter(risk_score__lte=30).count()},
            {'level': 'medium',   'count': qs.filter(risk_score__gt=30, risk_score__lte=60).count()},
            {'level': 'high',     'count': qs.filter(risk_score__gt=60, risk_score__lte=80).count()},
            {'level': 'critical', 'count': qs.filter(risk_score__gt=80).count()},
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def v2_kyc_read_notification(request, notif_id):
    """Mark a notification as read"""
    from ...models import KYCNotificationLog
    try:
        notif = KYCNotificationLog.objects.get(id=notif_id, user=request.user)
        notif.is_read = True; notif.read_at = timezone.now()
        notif.save(update_fields=['is_read', 'read_at'])
        return Response({'message': 'Marked as read'})
    except KYCNotificationLog.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def v2_kyc_risk_leaderboard(request):
    """Top 20 highest-risk KYCs"""
    from ...models import KYC
    from ...serializers import KYCAdminSerializer
    qs = KYC.objects.filter(status='pending').order_by('-risk_score')[:20]
    return Response(KYCAdminSerializer(qs, many=True).data)
