# api/referral/viewsets/ReferralCodeViewSet.py
# Referral code: generate, list, stats per code, custom alias
# ============================================================

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class ReferralCodeViewSet(APIView):
    """
    GET  /api/referral/codes/          — list all my codes
    POST /api/referral/codes/generate/ — generate new code
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.ReferralCodeService import ReferralCodeService
        # Ensure primary code exists
        ReferralCodeService.get_or_create_primary_code(request.user)
        codes = ReferralCodeService.get_code_stats(request.user)
        return Response({'success': True, 'codes': codes, 'total': len(codes)})

    def post(self, request):
        from api.referral.services.ReferralCodeService import ReferralCodeService

        custom_code = request.data.get('custom_code')
        source_tag = request.data.get('source_tag', '')
        campaign_id = request.data.get('campaign_id')
        expires_at = request.data.get('expires_at')

        result = ReferralCodeService.create_code(
            user=request.user,
            custom_code=custom_code,
            source_tag=source_tag,
            campaign_id=campaign_id,
            expires_at=expires_at,
        )

        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class ReferralCodeDetailView(APIView):
    """
    GET    /api/referral/codes/<code_id>/         — code detail + stats
    PATCH  /api/referral/codes/<code_id>/         — set custom alias
    DELETE /api/referral/codes/<code_id>/         — deactivate
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, code_id):
        from api.referral.models import ReferralCode

        try:
            code = ReferralCode.objects.get(
                id=code_id, user=request.user
            )
        except ReferralCode.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        return Response({
            'id': code.id,
            'code': code.code,
            'custom_code': code.custom_code,
            'active_code': code.get_active_code(),
            'source_tag': code.source_tag,
            'clicks': code.clicks,
            'unique_clicks': code.unique_clicks,
            'conversions': code.conversions,
            'conversion_rate': code.conversion_rate,
            'revenue_generated': float(code.revenue_generated),
            'is_primary': code.is_primary,
            'is_active': code.is_active,
            'is_expired': code.is_expired(),
            'expires_at': (
                code.expires_at.strftime('%Y-%m-%d') if code.expires_at else None
            ),
        })

    def patch(self, request, code_id):
        from api.referral.services.ReferralCodeService import ReferralCodeService

        custom_code = request.data.get('custom_code')
        if custom_code:
            result = ReferralCodeService.set_custom_code(
                code_id=code_id, user=request.user, custom_code=custom_code
            )
            if result['success']:
                return Response(result)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response({'error': 'No valid field to update'}, status=400)

    def delete(self, request, code_id):
        from api.referral.services.ReferralCodeService import ReferralCodeService

        result = ReferralCodeService.deactivate_code(
            code_id=code_id, user=request.user
        )
        if result['success']:
            return Response(result)
        return Response(result, status=400)


@api_view(['POST'])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def track_code_click(request, code_value):
    """GET /api/referral/codes/click/<code_value>/"""
    from api.referral.services.ReferralCodeService import ReferralCodeService

    ip = request.META.get('REMOTE_ADDR')
    tracked = ReferralCodeService.track_click(
        code_value=code_value, ip=ip
    )
    return Response({'tracked': tracked})
@permission_classes([IsAuthenticated])
def validate_code(request, code_value):
    """GET /api/referral/codes/validate/<code_value>/"""
    from api.referral.services.ReferralCodeService import ReferralCodeService

    result = ReferralCodeService.validate_code(code_value)
    if result['valid']:
        return Response({
            'valid': True,
            'referrer': result['user'].username,
            'code': result['code_value'],
        })
    return Response({'valid': False, 'error': result.get('error', 'Invalid')})