# api/referral/viewsets/ReferralFraudViewSet.py
# Admin: review suspicious referrals, manage blacklist
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class ReferralFraudViewSet(APIView):
    """
    GET /api/referral/admin/fraud/           — suspicious referrals list
    GET /api/referral/admin/fraud/stats/     — fraud overview stats
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import SuspiciousReferral

        status_filter = request.query_params.get('status', 'pending')
        min_score = int(request.query_params.get('min_score', 0))

        qs = SuspiciousReferral.objects.select_related(
            'referral', 'referral__referrer', 'referral__referred_user',
            'reviewed_by'
        ).order_by('-fraud_score', '-detected_at')

        if status_filter != 'all':
            qs = qs.filter(status=status_filter)

        if min_score > 0:
            qs = qs.filter(fraud_score__gte=min_score)

        qs = qs[:100]

        return Response({
            'success': True,
            'suspicious_referrals': [{
                'id': sr.id,
                'referral_id': sr.referral.id,
                'referrer': sr.referral.referrer.username,
                'referred_user': sr.referral.referred_user.username,
                'fraud_score': sr.fraud_score,
                'status': sr.status,
                'flags': sr.get_flag_list(),
                'evidence': sr.evidence,
                'review_notes': sr.review_notes,
                'reviewed_by': (
                    sr.reviewed_by.username if sr.reviewed_by else None
                ),
                'detected_at': sr.detected_at.strftime('%Y-%m-%d %H:%M'),
                'reviewed_at': (
                    sr.reviewed_at.strftime('%Y-%m-%d %H:%M')
                    if sr.reviewed_at else None
                ),
            } for sr in qs],
        })


class FraudReviewView(APIView):
    """
    POST /api/referral/admin/fraud/<sr_id>/clear/
    POST /api/referral/admin/fraud/<sr_id>/mark-fraud/
    """
    permission_classes = [IsAdminUser]

    def post(self, request, sr_id, action):
        from api.referral.models import SuspiciousReferral

        try:
            sr = SuspiciousReferral.objects.get(id=sr_id)
        except SuspiciousReferral.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        notes = request.data.get('notes', '')

        if action == 'clear':
            sr.clear(admin_user=request.user, notes=notes)
            return Response({'success': True, 'status': 'cleared'})

        elif action == 'mark-fraud':
            sr.mark_fraud(admin_user=request.user, notes=notes)

            # Initiate clawback if requested
            if request.data.get('initiate_clawback', False):
                from api.referral.services.CommissionClawbackService import CommissionClawbackService
                clawback_result = CommissionClawbackService.bulk_initiate_for_fraud(
                    referral_id=sr.referral.id,
                    reason_detail=notes,
                )
                return Response({
                    'success': True,
                    'status': 'fraud',
                    'clawbacks_initiated': clawback_result.get('initiated', 0),
                })

            return Response({'success': True, 'status': 'fraud'})

        return Response({'error': 'Invalid action'}, status=400)


class FraudScanView(APIView):
    """POST /api/referral/admin/fraud/scan/ — trigger fraud scan"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.ReferralFraudService import ReferralFraudService
        result = ReferralFraudService.scan_existing_referrals()
        return Response({'success': True, **result})


class BlacklistViewSet(APIView):
    """
    GET  /api/referral/admin/blacklist/      — list blacklist entries
    POST /api/referral/admin/blacklist/      — add entry
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import ReferralBlacklist

        qs = ReferralBlacklist.objects.filter(
            is_active=True
        ).order_by('-hit_count')[:100]

        return Response({
            'blacklist': [{
                'id': b.id,
                'pattern_type': b.pattern_type,
                'pattern_value': b.pattern_value,
                'severity': b.severity,
                'reason': b.reason,
                'hit_count': b.hit_count,
                'last_hit': (
                    b.last_hit_at.strftime('%Y-%m-%d')
                    if b.last_hit_at else None
                ),
                'created_at': b.created_at.strftime('%Y-%m-%d'),
            } for b in qs],
        })

    def post(self, request):
        from api.referral.services.ReferralFraudService import ReferralFraudService

        required = ['pattern_type', 'pattern_value', 'reason']
        for field in required:
            if not request.data.get(field):
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        result = ReferralFraudService.add_to_blacklist(
            pattern_type=request.data['pattern_type'],
            pattern_value=request.data['pattern_value'],
            reason=request.data['reason'],
            admin_user=request.user,
            severity=request.data.get('severity', 'high'),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class BlacklistDetailView(APIView):
    """DELETE /api/referral/admin/blacklist/<entry_id>/"""
    permission_classes = [IsAdminUser]

    def delete(self, request, entry_id):
        from api.referral.models import ReferralBlacklist
        try:
            entry = ReferralBlacklist.objects.get(id=entry_id)
            entry.is_active = False
            entry.save(update_fields=['is_active'])
            return Response({'success': True})
        except ReferralBlacklist.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)