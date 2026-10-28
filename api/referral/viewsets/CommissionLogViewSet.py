# api/referral/viewsets/CommissionLogViewSet.py
# Commission log: list, pending, held commissions
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class CommissionLogViewSet(APIView):
    """
    GET /api/referral/commissions/         — my commission logs
    GET /api/referral/commissions/pending/ — pending/held
    GET /api/referral/commissions/summary/ — summary stats
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.models import CommissionLog
        from django.db.models import Q

        days = min(365, int(request.query_params.get('days', 30)))
        level = request.query_params.get('level')
        status_filter = request.query_params.get('status')

        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)

        qs = CommissionLog.objects.filter(
            user=request.user,
            created_at__gte=cutoff,
        ).order_by('-created_at')

        if level:
            qs = qs.filter(level=int(level))

        if status_filter:
            qs = qs.filter(status=status_filter)

        logs = qs[:100]

        return Response({
            'success': True,
            'logs': [{
                'id': c.id,
                'from_user': c.referred_user.username,
                'amount': float(c.amount),
                'base_amount': float(c.base_amount),
                'commission_rate': float(c.commission_rate),
                'level': c.level,
                'action_type': c.action_type,
                'status': c.status,
                'source_reference': c.source_reference,
                'date': c.created_at.strftime('%Y-%m-%d %H:%M'),
                'release_at': (
                    c.hold.release_at.strftime('%Y-%m-%d')
                    if hasattr(c, 'hold') and c.hold else None
                ),
            } for c in logs],
        })


class CommissionPendingView(APIView):
    """GET /api/referral/commissions/pending/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.CommissionService import CommissionService
        data = CommissionService.get_pending_commissions(request.user)
        return Response({'success': True, **data})


class CommissionSummaryView(APIView):
    """GET /api/referral/commissions/summary/?days=30"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.CommissionService import CommissionService
        days = min(365, int(request.query_params.get('days', 30)))
        summary = CommissionService.get_commission_summary(request.user, days)
        return Response({'success': True, **summary})


class AdminCommissionReleaseView(APIView):
    """
    POST /api/referral/admin/commissions/<id>/release/
    Admin: manual commission release।
    """
    permission_classes = [IsAdminUser]

    def post(self, request, commission_id):
        from api.referral.services.CommissionService import CommissionService
        result = CommissionService.release_held_commission(
            commission_log_id=commission_id,
            admin_user=request.user,
        )
        if result['success']:
            return Response(result)
        return Response(result, status=400)


class AdminBulkReleaseView(APIView):
    """
    POST /api/referral/admin/commissions/bulk-release/
    Admin: release all expired holds।
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.CommissionService import CommissionService
        dry_run = request.data.get('dry_run', False)
        result = CommissionService.release_expired_holds(dry_run=dry_run)
        return Response({'success': True, **result})