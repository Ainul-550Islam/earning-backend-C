# kyc/compliance/__init__.py already exists
# kyc/compliance/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
import datetime


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_gdpr_erasure(request):
    """User requests GDPR data erasure (Right to be Forgotten)"""
    from .models import GDPRDataRequest
    from kyc.utils.audit_utils import get_client_ip

    existing = GDPRDataRequest.objects.filter(
        user=request.user, request_type='erasure', status='pending'
    ).first()
    if existing:
        return Response({'error': 'Erasure request already pending', 'id': existing.id}, status=400)

    req = GDPRDataRequest.create_erasure_request(
        user=request.user,
        reason=request.data.get('reason', ''),
        ip=get_client_ip(request),
    )
    return Response({
        'id':       req.id,
        'status':   req.status,
        'deadline': req.deadline,
        'message':  'Erasure request received. Will be processed within 30 days.',
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_data_export(request):
    """User requests data export (Right of Access)"""
    from kyc.gdpr.service import GDPRService
    from django.core.files.base import ContentFile
    from .models import GDPRDataRequest
    import json

    data = GDPRService.export_user_data(request.user)
    json_bytes = json.dumps(data, indent=2, default=str).encode('utf-8')

    req = GDPRDataRequest.objects.create(
        user=request.user,
        request_type='access',
        status='completed',
        deadline=timezone.now() + datetime.timedelta(days=30),
        completed_at=timezone.now(),
    )
    req.data_export_file.save(f'user_{request.user.id}_export.json', ContentFile(json_bytes))

    return Response({
        'id':       req.id,
        'status':   'completed',
        'download': req.data_export_file.url if req.data_export_file else None,
        'message':  'Data export ready.',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_consent(request):
    """Log user consent for KYC data processing"""
    from .models import ConsentLog
    from kyc.utils.audit_utils import get_client_ip, get_user_agent

    consent_type = request.data.get('consent_type')
    is_given     = request.data.get('is_given', True)
    version      = request.data.get('version', '1.0')

    if not consent_type:
        return Response({'error': 'consent_type is required'}, status=400)

    log = ConsentLog.objects.create(
        user=request.user,
        consent_type=consent_type,
        is_given=is_given,
        version=version,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        text_shown=request.data.get('text_shown', ''),
    )
    if not is_given:
        log.withdrawn_at = timezone.now()
        log.save(update_fields=['withdrawn_at'])

    return Response({
        'id':           log.id,
        'consent_type': log.consent_type,
        'is_given':     log.is_given,
        'created_at':   log.created_at,
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_consents(request):
    """Get user's current consent status"""
    from .models import ConsentLog
    latest = {}
    for log in ConsentLog.objects.filter(user=request.user).order_by('consent_type', '-created_at'):
        if log.consent_type not in latest:
            latest[log.consent_type] = {
                'consent_type': log.consent_type,
                'is_given':     log.is_given,
                'version':      log.version,
                'created_at':   log.created_at,
            }
    return Response(list(latest.values()))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def gdpr_requests_list(request):
    """Admin — All GDPR requests"""
    from .models import GDPRDataRequest
    qs = GDPRDataRequest.objects.all().order_by('-created_at')
    status_f = request.query_params.get('status')
    if status_f: qs = qs.filter(status=status_f)
    data = [{
        'id':           r.id,
        'username':     r.user.username,
        'request_type': r.request_type,
        'status':       r.status,
        'is_overdue':   r.is_overdue,
        'deadline':     r.deadline,
        'created_at':   r.created_at,
    } for r in qs[:100]]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def process_erasure(request, request_id):
    """Admin — Process a GDPR erasure request"""
    from .models import GDPRDataRequest
    from kyc.gdpr.service import GDPRService
    try:
        req = GDPRDataRequest.objects.get(id=request_id, request_type='erasure')
    except GDPRDataRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)

    action = request.data.get('action', 'approve')  # approve | reject
    if action == 'reject':
        req.status           = 'rejected'
        req.rejection_reason = request.data.get('reason', 'Legal obligation to retain data')
        req.handled_by       = request.user
        req.completed_at     = timezone.now()
        req.save()
        return Response({'message': 'Erasure request rejected', 'reason': req.rejection_reason})

    summary = GDPRService.handle_erasure_request(user=req.user, reason=req.reason, actor=request.user)
    req.status       = 'completed'
    req.handled_by   = request.user
    req.completed_at = timezone.now()
    req.save()
    return Response({'message': 'Erasure completed', 'summary': summary})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cdd_list(request):
    """Admin — CDD records"""
    from .models import CustomerDueDiligence
    from rest_framework import serializers as drf_serializers

    if request.method == 'GET':
        qs = CustomerDueDiligence.objects.select_related('user', 'kyc').all().order_by('-created_at')
        tier = request.query_params.get('tier')
        if tier: qs = qs.filter(tier=tier)
        overdue_only = request.query_params.get('overdue') == 'true'

        data = [{
            'id':              c.id,
            'username':        c.user.username,
            'tier':            c.tier,
            'risk_category':   c.risk_category,
            'is_edd_required': c.is_edd_required,
            'next_review_at':  c.next_review_at,
            'is_overdue':      c.is_overdue_for_review(),
        } for c in qs if not overdue_only or c.is_overdue_for_review()]
        return Response(data)

    # POST — create/update CDD record
    kyc_id = request.data.get('kyc_id')
    try:
        from kyc.models import KYC
        kyc = KYC.objects.get(id=kyc_id)
    except Exception:
        return Response({'error': 'KYC not found'}, status=404)

    cdd, _ = CustomerDueDiligence.objects.get_or_create(
        kyc=kyc, user=kyc.user,
        defaults={
            'tier':             request.data.get('tier', 'cdd'),
            'risk_category':    request.data.get('risk_category', 'medium'),
            'review_frequency': request.data.get('review_frequency', 'annual'),
            'is_edd_required':  request.data.get('is_edd_required', False),
            'edd_reason':       request.data.get('edd_reason', ''),
            'source_of_funds':  request.data.get('source_of_funds', ''),
            'source_of_wealth': request.data.get('source_of_wealth', ''),
        }
    )
    cdd.schedule_next_review()
    return Response({
        'id':              cdd.id,
        'tier':            cdd.tier,
        'next_review_at':  cdd.next_review_at,
        'is_edd_required': cdd.is_edd_required,
    }, status=201)
