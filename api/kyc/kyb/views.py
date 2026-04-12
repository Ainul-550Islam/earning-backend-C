# kyc/kyb/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from .models import BusinessVerification, UBODeclaration, BusinessDirector
from .serializers import BusinessVerificationSerializer, UBODeclarationSerializer, BusinessDirectorSerializer


# ── User Endpoints ─────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def my_business(request):
    """User's own business verification"""
    existing = BusinessVerification.objects.filter(user=request.user).first()

    if request.method == 'GET':
        if not existing:
            return Response({'status': 'not_submitted'})
        return Response(BusinessVerificationSerializer(existing, context={'request': request}).data)

    if existing and existing.status == 'verified':
        return Response({'error': 'Business already verified.'}, status=400)

    if existing:
        s = BusinessVerificationSerializer(existing, data=request.data, partial=True, context={'request': request})
        s.is_valid(raise_exception=True); s.save(); code = 200
    else:
        s = BusinessVerificationSerializer(data=request.data, context={'request': request})
        s.is_valid(raise_exception=True)
        s.save(user=request.user, status='pending'); code = 201

    return Response(BusinessVerificationSerializer(
        BusinessVerification.objects.get(user=request.user),
        context={'request': request}
    ).data, status=code)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_ubo(request):
    """Add UBO declaration for user's business"""
    biz = BusinessVerification.objects.filter(user=request.user).first()
    if not biz:
        return Response({'error': 'No business verification found. Submit business first.'}, status=404)
    s = UBODeclarationSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    ubo = s.save(business=biz)
    return Response(UBODeclarationSerializer(ubo).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_director(request):
    """Add director for user's business"""
    biz = BusinessVerification.objects.filter(user=request.user).first()
    if not biz:
        return Response({'error': 'No business verification found.'}, status=404)
    s = BusinessDirectorSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    director = s.save(business=biz)
    return Response(BusinessDirectorSerializer(director).data, status=201)


# ── Admin Endpoints ────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyb_admin_list(request):
    """Admin — All business verifications"""
    qs = BusinessVerification.objects.select_related('user').all().order_by('-created_at')
    status_f = request.query_params.get('status')
    if status_f: qs = qs.filter(status=status_f)
    search = request.query_params.get('search')
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(business_name__icontains=search) | Q(trade_license_no__icontains=search))
    return Response(BusinessVerificationSerializer(qs, many=True, context={'request': request}).data)


@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyb_admin_review(request, kyb_id):
    """Admin — Review business verification"""
    try:
        biz = BusinessVerification.objects.get(id=kyb_id)
    except BusinessVerification.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        return Response(BusinessVerificationSerializer(biz, context={'request': request}).data)

    if request.method == 'PATCH':
        s = BusinessVerificationSerializer(biz, data=request.data, partial=True, context={'request': request})
        s.is_valid(raise_exception=True); s.save()
        return Response(BusinessVerificationSerializer(biz, context={'request': request}).data)

    # POST — approve/reject
    action = request.data.get('status')
    if action == 'verified':
        biz.approve(reviewed_by=request.user)
    elif action == 'rejected':
        reason = request.data.get('rejection_reason', '')
        if not reason: return Response({'error': 'rejection_reason required'}, status=400)
        biz.reject(reason=reason, reviewed_by=request.user)
    else:
        return Response({'error': 'Invalid status. Use: verified | rejected'}, status=400)

    return Response(BusinessVerificationSerializer(biz, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def kyb_verify_ubo(request, ubo_id):
    """Admin — Verify an UBO"""
    from django.utils import timezone
    try:
        ubo = UBODeclaration.objects.get(id=ubo_id)
    except UBODeclaration.DoesNotExist:
        return Response({'error': 'UBO not found'}, status=404)
    ubo.is_verified = True; ubo.verified_at = timezone.now(); ubo.save()
    return Response({'message': 'UBO verified', 'id': ubo_id})
