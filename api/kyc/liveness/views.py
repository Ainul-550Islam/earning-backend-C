# kyc/liveness/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import LivenessCheck
from .service import LivenessService


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def run_liveness_check(request):
    """
    User submits selfie → liveness + deepfake check.
    POST: { selfie: <image>, provider: 'mock'|'aws_rekognition' }
    """
    from kyc.models import KYC
    selfie   = request.FILES.get('selfie')
    if not selfie:
        return Response({'error': 'selfie image is required'}, status=400)

    kyc = KYC.objects.filter(user=request.user).first()
    if not kyc:
        return Response({'error': 'KYC record not found. Submit KYC first.'}, status=404)

    provider  = request.data.get('provider', 'mock')
    service   = LivenessService(provider=provider)

    # Run liveness
    result    = service.check(kyc=kyc, image_file=selfie, check_type='passive')

    # Run deepfake detection
    if hasattr(selfie, 'seek'): selfie.seek(0)
    deepfake  = service.detect_deepfake(selfie)
    result.update({
        'is_deepfake': deepfake['is_synthetic'],
        'deepfake_probability': deepfake['deepfake_probability'],
    })

    check = service.save_result(kyc, result)

    return Response({
        'id':            check.id,
        'result':        check.result,
        'passed':        check.passed,
        'liveness_score': check.liveness_score,
        'is_deepfake':   check.is_deepfake,
        'is_spoof_detected': check.is_spoof_detected,
        'deepfake_probability': deepfake['deepfake_probability'],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_liveness_history(request):
    """User's own liveness check history"""
    from kyc.models import KYC
    kyc = KYC.objects.filter(user=request.user).first()
    if not kyc:
        return Response([])
    checks = LivenessCheck.objects.filter(kyc=kyc).order_by('-created_at')[:10]
    return Response([{
        'id':            c.id,
        'check_type':    c.check_type,
        'provider':      c.provider,
        'result':        c.result,
        'liveness_score': c.liveness_score,
        'passed':        c.passed,
        'created_at':    c.created_at,
    } for c in checks])


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def liveness_admin_list(request):
    """Admin — All liveness checks with filters"""
    qs = LivenessCheck.objects.select_related('user', 'kyc').all().order_by('-created_at')
    result_f = request.query_params.get('result')
    if result_f: qs = qs.filter(result=result_f)
    deepfake_only = request.query_params.get('deepfake') == 'true'
    if deepfake_only: qs = qs.filter(is_deepfake=True)
    limit = int(request.query_params.get('limit', 50))
    return Response([{
        'id':            c.id,
        'username':      c.user.username if c.user else None,
        'kyc_id':        c.kyc_id,
        'check_type':    c.check_type,
        'provider':      c.provider,
        'result':        c.result,
        'liveness_score': c.liveness_score,
        'is_deepfake':   c.is_deepfake,
        'is_spoof_detected': c.is_spoof_detected,
        'created_at':    c.created_at,
    } for c in qs[:limit]])
