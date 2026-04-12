# kyc/views.py  ── WORLD #1 COMPLETE — সব endpoint সহ (existing + new)
import logging
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone

from .models import (
    KYC, KYCVerificationLog, KYCSubmission,
    KYCBlacklist, KYCRiskProfile, KYCOCRResult, KYCFaceMatchResult,
    KYCWebhookEndpoint, KYCWebhookDeliveryLog, KYCExportJob,
    KYCBulkActionLog, KYCAdminNote, KYCRejectionTemplate,
    KYCAnalyticsSnapshot, KYCIPTracker, KYCVerificationStep,
    KYCOTPLog, KYCTenantConfig, KYCAuditTrail, KYCNotificationLog,
    KYCFeatureFlag, KYCDuplicateGroup,
)
from .serializers import (
    KYCSerializer, KYCAdminSerializer, KYCSubmissionSerializer,
    KYCBlacklistSerializer, KYCRiskProfileSerializer, KYCOCRResultSerializer,
    KYCAdminNoteSerializer, KYCRejectionTemplateSerializer,
    KYCAnalyticsSerializer, KYCTenantConfigSerializer,
    KYCWebhookEndpointSerializer, KYCAuditTrailSerializer,
    KYCFeatureFlagSerializer, KYCDuplicateGroupSerializer,
    KYCExportJobSerializer, KYCNotificationLogSerializer,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  USER ENDPOINTS  (existing — unchanged)
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_status(request):
    """GET current user's KYCSubmission status (UI contract)"""
    submission = KYCSubmission.objects.filter(user=request.user).order_by("-submitted_at", "-created_at").first()
    if not submission:
        return Response({"status": "not_submitted", "verification_progress": 0, "document_type": None})
    return Response(KYCSubmissionSerializer(submission, context={"request": request}).data)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def kyc_submit(request):
    """GET/POST/DELETE for current user's KYCSubmission."""
    existing = KYCSubmission.objects.filter(user=request.user).order_by("-submitted_at", "-created_at").first()

    if request.method == "GET":
        if not existing:
            return Response({"status": "not_submitted", "verification_progress": 0})
        return Response(KYCSubmissionSerializer(existing, context={"request": request}).data)

    if request.method == "DELETE":
        if not existing:
            return Response({"error": "KYC submission not found"}, status=404)
        if existing.status == KYCSubmission.StatusChoices.VERIFIED:
            return Response({"error": "Verified KYC delete is not allowed"}, status=400)
        existing.delete()
        return Response({"message": "KYC submission deleted successfully"})

    if request.method == "POST":
        if existing and existing.status == KYCSubmission.StatusChoices.VERIFIED:
            return Response({"error": "KYC already verified"}, status=400)
        if existing:
            serializer = KYCSubmissionSerializer(existing, data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True); serializer.save(); status_code = 200
        else:
            serializer = KYCSubmissionSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True); serializer.save(); status_code = 201
        submission = KYCSubmission.objects.filter(user=request.user).order_by("-submitted_at", "-created_at").first()
        return Response(KYCSubmissionSerializer(submission, context={"request": request}).data, status=status_code)

    return Response({"error": "Method not allowed"}, status=405)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def kyc_fraud_check(request):
    """POST: compute fraud/audit placeholder scores and move progress to 60-75%."""
    submission = KYCSubmission.objects.filter(user=request.user).order_by("-submitted_at", "-created_at").first()
    if not submission:
        return Response({"error": "KYC submission not found"}, status=404)
    if submission.status in [KYCSubmission.StatusChoices.VERIFIED, KYCSubmission.StatusChoices.REJECTED]:
        return Response({"error": f"KYC already finalized: {submission.status}"}, status=400)

    nid_front_size = getattr(submission.nid_front, "size", 0) or 0
    nid_back_size  = getattr(submission.nid_back,  "size", 0) or 0
    selfie_size    = getattr(submission.selfie_with_note, "size", 0) or 0

    image_clarity_score     = max(0.0, min(100.0, 30.0 + (nid_front_size % 70000) / 70000 * 70.0))
    document_matching_score = max(0.0, min(100.0, 25.0 + ((nid_front_size + nid_back_size) % 120000) / 120000 * 75.0))
    selfie_mod              = (selfie_size % 1000)
    face_liveness_check     = KYCSubmission.FaceLivenessChoices.SUCCESS if selfie_mod < 650 else KYCSubmission.FaceLivenessChoices.FAILURE
    progress                = 60 + (int(nid_back_size) % 16)

    submission.set_fraud_check_results(
        clarity=image_clarity_score, matching=document_matching_score,
        liveness=face_liveness_check, progress=progress,
    )
    return Response(KYCSubmissionSerializer(submission, context={"request": request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_logs(request):
    """User এর নিজের KYC logs"""
    try:
        kyc  = KYC.objects.get(user=request.user)
        logs = kyc.kyc_kycverificationlog_tenant.all().values('action', 'details', 'created_at')
        return Response(list(logs))
    except KYC.DoesNotExist:
        return Response([])


# ══════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS  (existing — unchanged)
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
    today = timezone.now().date()
    qs    = KYC.objects.all()
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

    if request.method == 'GET':
        return Response(KYCAdminSerializer(kyc).data)

    if request.method == 'PATCH':
        for field in ['full_name','date_of_birth','phone_number','payment_number',
                      'payment_method','address_line','city','country','document_type','document_number','admin_notes']:
            if field in request.data:
                setattr(kyc, field, request.data[field])
        kyc.save()
        KYCVerificationLog.objects.create(kyc=kyc, action='edited', performed_by=request.user, details='Admin edited KYC info')
        return Response(KYCAdminSerializer(kyc).data)

    new_status = request.data.get('status')
    if not new_status:
        return Response({'error': 'status field required'}, status=400)

    if new_status == 'verified':
        kyc.approve(reviewed_by=request.user); log_action = 'approved'
        log_detail = request.data.get('admin_notes', 'KYC approved by admin')
    elif new_status == 'rejected':
        reason = request.data.get('rejection_reason', '')
        if not reason: return Response({'error': 'rejection_reason required'}, status=400)
        kyc.reject(reason=reason, reviewed_by=request.user); log_action = 'rejected'; log_detail = reason
    else:
        kyc.status = new_status
        if 'admin_notes' in request.data: kyc.admin_notes = request.data['admin_notes']
        kyc.save(); log_action = 'status_updated'; log_detail = f'Status changed to {new_status}'

    KYCVerificationLog.objects.create(kyc=kyc, action=log_action, performed_by=request.user, details=log_detail)
    return Response(KYCAdminSerializer(kyc).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_delete(request, kyc_id):
    try:
        kyc = KYC.objects.get(id=kyc_id); name = kyc.full_name or str(kyc.user); kyc.delete()
        return Response({'message': f'{name} এর KYC deleted'})
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_reset(request, kyc_id):
    try:
        kyc = KYC.objects.get(id=kyc_id)
        kyc.status = 'pending'; kyc.rejection_reason = ''; kyc.reviewed_by = None; kyc.reviewed_at = None; kyc.save()
        KYCVerificationLog.objects.create(kyc=kyc, action='reset', performed_by=request.user, details='KYC reset to pending by admin')
        return Response(KYCAdminSerializer(kyc).data)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_logs(request, kyc_id):
    try:
        kyc  = KYC.objects.get(id=kyc_id)
        logs = kyc.kyc_kycverificationlog_tenant.select_related('performed_by').all().order_by('-created_at')
        data = [{'action': l.action, 'details': l.details, 'created_at': l.created_at,
                 'performed_by__username': l.performed_by.username if l.performed_by else None} for l in logs]
        return Response(data)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_add_note(request, kyc_id):
    try:
        kyc  = KYC.objects.get(id=kyc_id)
        note = request.data.get('note', '').strip()
        if not note: return Response({'error': 'note is required'}, status=400)
        existing  = kyc.admin_notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        kyc.admin_notes = f"{existing}\n[{timestamp}] {request.user.username}: {note}".strip()
        kyc.save()
        KYCVerificationLog.objects.create(kyc=kyc, action='note_added', performed_by=request.user, details=note)
        return Response({'message': 'Note added', 'admin_notes': kyc.admin_notes})
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_admin_bulk_action(request):
    """Admin — Bulk approve/reject/pending"""
    ids    = request.data.get('ids', [])
    action = request.data.get('action', '')
    if not ids: return Response({'error': 'ids required'}, status=400)
    if action not in ['verified', 'rejected', 'pending']: return Response({'error': 'Invalid action'}, status=400)

    kycs = KYC.objects.filter(id__in=ids)
    done = 0
    for kyc in kycs:
        try:
            if action == 'verified':
                kyc.approve(reviewed_by=request.user); log_action = 'approved'
            elif action == 'rejected':
                reason = request.data.get('rejection_reason', 'Bulk rejected by admin')
                kyc.reject(reason=reason, reviewed_by=request.user); log_action = 'rejected'
            else:
                kyc.status = 'pending'; kyc.save(); log_action = 'status_updated'
            KYCVerificationLog.objects.create(kyc=kyc, action=log_action, performed_by=request.user, details=f'Bulk action: {action}')
            done += 1
        except Exception as e:
            logger.error(f'Bulk action error for KYC {kyc.id}: {e}')

    return Response({'message': f'{done} records updated to {action}', 'updated': done})


# ══════════════════════════════════════════════════════════════
#  NEW ENDPOINTS — World #1 Features
# ══════════════════════════════════════════════════════════════

# ── Blacklist ──────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_blacklist_list(request):
    """Admin — Blacklist list + add"""
    if request.method == 'GET':
        qs = KYCBlacklist.objects.filter(is_active=True).order_by('-created_at')
        btype = request.query_params.get('type')
        if btype: qs = qs.filter(type=btype)
        return Response(KYCBlacklistSerializer(qs, many=True).data)

    serializer = KYCBlacklistSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(added_by=request.user)
    return Response(KYCBlacklistSerializer(obj).data, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_blacklist_detail(request, pk):
    try:
        obj = KYCBlacklist.objects.get(pk=pk)
    except KYCBlacklist.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        return Response(KYCBlacklistSerializer(obj).data)
    if request.method == 'PATCH':
        serializer = KYCBlacklistSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True); serializer.save()
        return Response(KYCBlacklistSerializer(obj).data)
    obj.is_active = False; obj.save()
    return Response({'message': 'Blacklist entry deactivated'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kyc_blacklist_check(request):
    """Check if value is blacklisted (user-facing, non-admin)"""
    btype = request.data.get('type')
    value = request.data.get('value')
    if not btype or not value:
        return Response({'error': 'type and value are required'}, status=400)
    is_bl = KYCBlacklist.is_blacklisted(btype, value)
    return Response({'is_blacklisted': is_bl, 'type': btype, 'value': value})


# ── Risk Profile ───────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_risk_profile(request, kyc_id):
    """Admin — KYC risk profile"""
    try:
        kyc     = KYC.objects.get(id=kyc_id)
        profile, _ = KYCRiskProfile.objects.get_or_create(kyc=kyc)
        return Response(KYCRiskProfileSerializer(profile).data)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_risk_recompute(request, kyc_id):
    """Admin — Recompute risk score"""
    try:
        kyc = KYC.objects.get(id=kyc_id)
        kyc.calculate_risk_score()
        profile, _ = KYCRiskProfile.objects.get_or_create(kyc=kyc)
        profile.overall_score = kyc.risk_score
        profile.compute()
        return Response(KYCRiskProfileSerializer(profile).data)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)


# ── Admin Notes ────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_notes_list(request, kyc_id):
    try:
        kyc = KYC.objects.get(id=kyc_id)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)

    if request.method == 'GET':
        notes = KYCAdminNote.objects.filter(kyc=kyc).order_by('-is_pinned', '-created_at')
        return Response(KYCAdminNoteSerializer(notes, many=True).data)

    serializer = KYCAdminNoteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    note = serializer.save(kyc=kyc, author=request.user)
    return Response(KYCAdminNoteSerializer(note).data, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_note_detail(request, kyc_id, note_id):
    try:
        note = KYCAdminNote.objects.get(id=note_id, kyc_id=kyc_id)
    except KYCAdminNote.DoesNotExist:
        return Response({'error': 'Note not found'}, status=404)

    if request.method == 'DELETE':
        note.delete(); return Response({'message': 'Note deleted'})
    serializer = KYCAdminNoteSerializer(note, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True); serializer.save()
    return Response(KYCAdminNoteSerializer(note).data)


# ── Rejection Templates ────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_rejection_templates(request):
    if request.method == 'GET':
        qs = KYCRejectionTemplate.objects.filter(is_active=True).order_by('-usage_count', 'title')
        return Response(KYCRejectionTemplateSerializer(qs, many=True).data)
    serializer = KYCRejectionTemplateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save()
    return Response(KYCRejectionTemplateSerializer(obj).data, status=201)


# ── Analytics ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_analytics(request):
    """Analytics snapshots"""
    period = request.query_params.get('period', 'daily')
    limit  = int(request.query_params.get('limit', 30))
    qs = KYCAnalyticsSnapshot.objects.filter(period=period).order_by('-period_start')[:limit]
    return Response(KYCAnalyticsSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_analytics_summary(request):
    """Full analytics summary for dashboard"""
    from django.db.models import Sum, Avg, Count
    qs    = KYC.objects.all()
    today = timezone.now().date()
    data  = {
        'total':           qs.count(),
        'verified':        qs.filter(status='verified').count(),
        'rejected':        qs.filter(status='rejected').count(),
        'pending':         qs.filter(status='pending').count(),
        'high_risk':       qs.filter(risk_score__gt=60).count(),
        'today':           qs.filter(created_at__date=today).count(),
        'avg_risk_score':  qs.aggregate(avg=Avg('risk_score'))['avg'] or 0,
        'duplicates':      qs.filter(is_duplicate=True).count(),
        'by_doc_type': list(qs.values('document_type').annotate(count=Count('id')).order_by('-count')),
        'by_status':   list(qs.values('status').annotate(count=Count('id')).order_by('-count')),
    }
    return Response(data)


# ── Tenant Config ──────────────────────────────────────────────

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_tenant_config(request):
    """Get/update KYC config for current tenant"""
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant associated with this user'}, status=400)
    config = KYCTenantConfig.for_tenant(tenant)

    if request.method == 'GET':
        return Response(KYCTenantConfigSerializer(config).data)
    partial = request.method == 'PATCH'
    serializer = KYCTenantConfigSerializer(config, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True); serializer.save()
    return Response(KYCTenantConfigSerializer(config).data)


# ── Webhook Endpoints ──────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_webhooks_list(request):
    tenant = getattr(request.user, 'tenant', None)
    if request.method == 'GET':
        qs = KYCWebhookEndpoint.objects.filter(tenant=tenant) if tenant else KYCWebhookEndpoint.objects.all()
        return Response(KYCWebhookEndpointSerializer(qs, many=True).data)
    serializer = KYCWebhookEndpointSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(tenant=tenant)
    return Response(KYCWebhookEndpointSerializer(obj).data, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_webhook_detail(request, pk):
    try:
        obj = KYCWebhookEndpoint.objects.get(pk=pk)
    except KYCWebhookEndpoint.DoesNotExist:
        return Response({'error': 'Webhook not found'}, status=404)
    if request.method == 'GET':
        return Response(KYCWebhookEndpointSerializer(obj).data)
    if request.method == 'DELETE':
        obj.delete(); return Response({'message': 'Webhook deleted'})
    s = KYCWebhookEndpointSerializer(obj, data=request.data, partial=True)
    s.is_valid(raise_exception=True); s.save()
    return Response(KYCWebhookEndpointSerializer(obj).data)


# ── Audit Trail ────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_audit_trail(request):
    """Admin — Full audit trail"""
    qs = KYCAuditTrail.objects.all().order_by('-created_at')
    entity_type = request.query_params.get('entity_type')
    entity_id   = request.query_params.get('entity_id')
    if entity_type: qs = qs.filter(entity_type=entity_type)
    if entity_id:   qs = qs.filter(entity_id=entity_id)
    limit = int(request.query_params.get('limit', 50))
    return Response(KYCAuditTrailSerializer(qs[:limit], many=True).data)


# ── Feature Flags ──────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_feature_flags(request):
    if request.method == 'GET':
        qs = KYCFeatureFlag.objects.all().order_by('key')
        return Response(KYCFeatureFlagSerializer(qs, many=True).data)
    s = KYCFeatureFlagSerializer(data=request.data)
    s.is_valid(raise_exception=True); obj = s.save(updated_by=request.user)
    return Response(KYCFeatureFlagSerializer(obj).data, status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_feature_flag_toggle(request, key):
    """Toggle a feature flag on/off"""
    tenant = getattr(request.user, 'tenant', None)
    obj, _ = KYCFeatureFlag.objects.get_or_create(key=key, tenant=tenant, defaults={'description': key})
    obj.is_enabled = not obj.is_enabled; obj.updated_by = request.user; obj.save()
    return Response({'key': key, 'is_enabled': obj.is_enabled})


# ── Duplicate Groups ───────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_duplicate_groups(request):
    """Admin — All duplicate groups"""
    resolved = request.query_params.get('resolved', 'false').lower() == 'true'
    qs = KYCDuplicateGroup.objects.filter(is_resolved=resolved).order_by('-created_at')
    return Response(KYCDuplicateGroupSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_duplicate_resolve(request, pk):
    """Resolve a duplicate group"""
    try:
        group = KYCDuplicateGroup.objects.get(pk=pk)
    except KYCDuplicateGroup.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    group.is_resolved    = True
    group.resolution_note = request.data.get('note', '')
    group.resolved_by   = request.user
    group.resolved_at   = timezone.now()
    group.save()
    return Response({'message': 'Duplicate group resolved', 'id': pk})


# ── Export Jobs ────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_exports(request):
    if request.method == 'GET':
        qs = KYCExportJob.objects.filter(requested_by=request.user).order_by('-created_at')[:20]
        return Response(KYCExportJobSerializer(qs, many=True).data)
    fmt = request.data.get('format', 'csv')
    filters_data = request.data.get('filters', {})
    tenant = getattr(request.user, 'tenant', None)
    job = KYCExportJob.objects.create(
        requested_by=request.user, tenant=tenant, format=fmt,
        filters=filters_data, status='pending',
    )
    # Trigger async task (if Celery available)
    try:
        from .tasks.export_tasks import export_kyc_data
        export_kyc_data.delay(job.id)
    except Exception:
        pass
    return Response(KYCExportJobSerializer(job).data, status=202)


# ── Notification Logs ──────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_my_notifications(request):
    """User's own KYC notifications"""
    qs = KYCNotificationLog.objects.filter(user=request.user).order_by('-created_at')[:50]
    return Response(KYCNotificationLogSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyc_all_notifications(request):
    """Admin — All KYC notifications"""
    qs = KYCNotificationLog.objects.all().order_by('-created_at')
    limit = int(request.query_params.get('limit', 100))
    return Response(KYCNotificationLogSerializer(qs[:limit], many=True).data)


# ── Health Check ───────────────────────────────────────────────

@api_view(['GET'])
def kyc_health(request):
    """KYC service health check"""
    return Response({
        'status': 'ok',
        'service': 'kyc',
        'version': '2.0.0',
        'timestamp': timezone.now().isoformat(),
    })
