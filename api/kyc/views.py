# kyc/views.py  ── 100% COMPLETE — সব endpoint সহ
import logging
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone

from .models import KYC, KYCVerificationLog
from .serializers import KYCSerializer, KYCAdminSerializer
from .forms import KYCSubmissionForm

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  USER ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_status(request):
    """User এর KYC status"""
    try:
        kyc = KYC.objects.get(user=request.user)
        return Response(KYCSerializer(kyc).data)
    except KYC.DoesNotExist:
        return Response({'status': 'not_submitted'})


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def kyc_submit(request):
    """User KYC submit / view / delete"""

    # ── READ ──────────────────────────────────────────────────
    if request.method == 'GET':
        try:
            kyc = KYC.objects.get(user=request.user)
            return Response(KYCSerializer(kyc).data)
        except KYC.DoesNotExist:
            return Response({'status': 'not_submitted'})

    # ── DELETE (user নিজে) ─────────────────────────────────────
    if request.method == 'DELETE':
        try:
            kyc = KYC.objects.get(user=request.user)
            if kyc.status == 'verified':
                return Response({'error': 'Verified KYC delete করা যাবে না'}, status=400)
            kyc.delete()
            return Response({'message': 'KYC deleted successfully'})
        except KYC.DoesNotExist:
            return Response({'error': 'KYC not found'}, status=404)

    # ── CREATE / UPDATE ────────────────────────────────────────
    form = KYCSubmissionForm(request.data)
    if not form.is_valid():
        return Response({'errors': form.errors}, status=400)

    data = form.cleaned_data
    kyc, created = KYC.objects.get_or_create(user=request.user)

    if kyc.status == 'verified':
        return Response({'error': 'KYC already verified'}, status=400)

    for field in ['full_name', 'date_of_birth', 'phone_number', 'payment_number',
                  'payment_method', 'address_line', 'city', 'country',
                  'document_type', 'document_number']:
        if field in data and data[field]:
            setattr(kyc, field, data[field])

    if 'document_front' in request.FILES:
        kyc.document_front = request.FILES['document_front']
    if 'document_back' in request.FILES:
        kyc.document_back = request.FILES['document_back']
    if 'selfie_photo' in request.FILES:
        kyc.selfie_photo = request.FILES['selfie_photo']

    kyc.status = 'pending'
    kyc.save()

    KYCVerificationLog.objects.create(
        kyc=kyc,
        action='submitted',
        performed_by=request.user,
        details='User submitted KYC for review'
    )

    return Response(KYCSerializer(kyc).data, status=201 if created else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_logs(request):
    """User এর নিজের KYC logs"""
    try:
        kyc = KYC.objects.get(user=request.user)
        logs = kyc.logs.all().values('action', 'details', 'created_at')
        return Response(list(logs))
    except KYC.DoesNotExist:
        return Response([])


# ══════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_list(request):
    """Admin — সব user এর KYC list"""
    status_filter = request.query_params.get('status', None)
    qs = KYC.objects.select_related('user').all().order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return Response(KYCAdminSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_stats(request):
    """Admin — Dashboard stats"""
    from django.utils import timezone as tz
    import datetime

    today = tz.now().date()
    qs = KYC.objects.all()

    stats = {
        'total':           qs.count(),
        'pending':         qs.filter(status='pending').count(),
        'verified':        qs.filter(status='verified').count(),
        'rejected':        qs.filter(status='rejected').count(),
        'not_submitted':   qs.filter(status='not_submitted').count(),
        'expired':         qs.filter(status='expired').count(),
        'high_risk':       qs.filter(risk_score__gt=60).count(),
        'duplicates':      qs.filter(is_duplicate=True).count(),
        'submitted_today': qs.filter(created_at__date=today).count(),
    }
    return Response(stats)


@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_review(request, kyc_id):
    """Admin — KYC review (approve/reject) + edit (PATCH)"""
    try:
        kyc = KYC.objects.get(id=kyc_id)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)

    # ── READ ───────────────────────────────────────────────────
    if request.method == 'GET':
        return Response(KYCAdminSerializer(kyc).data)

    # ── EDIT (PATCH) ───────────────────────────────────────────
    if request.method == 'PATCH':
        editable_fields = [
            'full_name', 'date_of_birth', 'phone_number', 'payment_number',
            'payment_method', 'address_line', 'city', 'country',
            'document_type', 'document_number', 'admin_notes',
        ]
        for field in editable_fields:
            if field in request.data:
                setattr(kyc, field, request.data[field])
        kyc.save()

        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='edited',
            performed_by=request.user,
            details=f'Admin edited KYC info'
        )
        return Response(KYCAdminSerializer(kyc).data)

    # ── REVIEW (POST — approve/reject/pending) ─────────────────
    new_status = request.data.get('status')
    if not new_status:
        return Response({'error': 'status field required'}, status=400)

    if new_status == 'verified':
        kyc.approve(reviewed_by=request.user)
        log_action = 'approved'
        log_detail = request.data.get('admin_notes', 'KYC approved by admin')

    elif new_status == 'rejected':
        reason = request.data.get('rejection_reason', '')
        if not reason:
            return Response({'error': 'rejection_reason required'}, status=400)
        kyc.reject(reason=reason, reviewed_by=request.user)
        log_action = 'rejected'
        log_detail = reason

    else:  # pending or any other
        kyc.status = new_status
        if 'admin_notes' in request.data:
            kyc.admin_notes = request.data['admin_notes']
        kyc.save()
        log_action = 'status_updated'
        log_detail = f'Status changed to {new_status}'

    KYCVerificationLog.objects.create(
        kyc=kyc,
        action=log_action,
        performed_by=request.user,
        details=log_detail
    )
    return Response(KYCAdminSerializer(kyc).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_delete(request, kyc_id):
    """Admin — KYC delete"""
    try:
        kyc = KYC.objects.get(id=kyc_id)
        name = kyc.full_name or str(kyc.user)
        kyc.delete()
        return Response({'message': f'{name} এর KYC deleted'})
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_reset(request, kyc_id):
    """Admin — KYC reset to pending"""
    try:
        kyc = KYC.objects.get(id=kyc_id)
        kyc.status = 'pending'
        kyc.rejection_reason = ''
        kyc.reviewed_by = None
        kyc.reviewed_at = None
        kyc.save()

        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='reset',
            performed_by=request.user,
            details='KYC reset to pending by admin'
        )
        return Response(KYCAdminSerializer(kyc).data)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_logs(request, kyc_id):
    """Admin — নির্দিষ্ট KYC এর audit logs"""
    try:
        kyc = KYC.objects.get(id=kyc_id)
        logs = kyc.logs.select_related('performed_by').all().order_by('-created_at')
        data = []
        for log in logs:
            data.append({
                'action': log.action,
                'details': log.details,
                'created_at': log.created_at,
                'performed_by__username': log.performed_by.username if log.performed_by else None,
            })
        return Response(data)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_add_note(request, kyc_id):
    """Admin — Note add করো"""
    try:
        kyc = KYC.objects.get(id=kyc_id)
        note = request.data.get('note', '').strip()
        if not note:
            return Response({'error': 'note is required'}, status=400)

        # Append to admin_notes
        existing = kyc.admin_notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        kyc.admin_notes = f"{existing}\n[{timestamp}] {request.user.username}: {note}".strip()
        kyc.save()

        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='note_added',
            performed_by=request.user,
            details=note
        )
        return Response({'message': 'Note added', 'admin_notes': kyc.admin_notes})
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_bulk_action(request):
    """Admin — Bulk approve/reject/pending"""
    ids = request.data.get('ids', [])
    action = request.data.get('action', '')

    if not ids:
        return Response({'error': 'ids required'}, status=400)
    if action not in ['verified', 'rejected', 'pending']:
        return Response({'error': 'Invalid action'}, status=400)

    kycs = KYC.objects.filter(id__in=ids)
    done = 0
    for kyc in kycs:
        try:
            if action == 'verified':
                kyc.approve(reviewed_by=request.user)
                log_action = 'approved'
            elif action == 'rejected':
                reason = request.data.get('rejection_reason', 'Bulk rejected by admin')
                kyc.reject(reason=reason, reviewed_by=request.user)
                log_action = 'rejected'
            else:
                kyc.status = 'pending'
                kyc.save()
                log_action = 'status_updated'

            KYCVerificationLog.objects.create(
                kyc=kyc,
                action=log_action,
                performed_by=request.user,
                details=f'Bulk action: {action}'
            )
            done += 1
        except Exception as e:
            logger.error(f'Bulk action error for KYC {kyc.id}: {e}')

    return Response({'message': f'{done} records updated to {action}', 'updated': done})