# api/referral/viewsets/AdminReferralViewSet.py
# Admin: bulk operations, clawback management, export
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)


class AdminReferralViewSet(APIView):
    """
    GET  /api/referral/admin/bulk/stats/      — platform overview
    POST /api/referral/admin/bulk/recalc/     — recalculate all trees
    POST /api/referral/admin/bulk/snapshots/  — take all tree snapshots
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import (
            Referral, ReferralEarning, ReferralChain,
            CommissionLog, SuspiciousReferral,
        )
        from django.db.models import Sum, Count, Q

        total_referrals = Referral.objects.count()
        total_commission = ReferralEarning.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        suspicious = Referral.objects.filter(is_suspicious=True).count()

        pending_commission = CommissionLog.objects.filter(
            status__in=['pending', 'held']
        ).aggregate(total=Sum('amount'))['total'] or 0

        fraud_pending = SuspiciousReferral.objects.filter(
            status='pending'
        ).count()

        return Response({
            'success': True,
            'stats': {
                'total_referrals': total_referrals,
                'level1': Referral.objects.count(),
                'level2': ReferralChain.objects.filter(level=2).count(),
                'level3': ReferralChain.objects.filter(level=3).count(),
                'total_commission_paid': float(total_commission),
                'pending_commission': float(pending_commission),
                'suspicious_referrals': suspicious,
                'fraud_pending_review': fraud_pending,
                'active_referrals': Referral.objects.filter(
                    referred_user__is_active=True
                ).count(),
                'unique_referrers': Referral.objects.values(
                    'referrer'
                ).distinct().count(),
            },
        })


class AdminBulkTreeRecalcView(APIView):
    """POST /api/referral/admin/bulk/recalc-trees/"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.ReferralTreeService import ReferralTreeService

        result = ReferralTreeService.rebuild_all_trees()
        return Response({'success': True, **result})


class AdminBulkSnapshotView(APIView):
    """POST /api/referral/admin/bulk/snapshots/"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )

        period = request.data.get('period', 'daily')
        count = ReferralAnalyticsService.snapshot_top_referrers(period=period)
        return Response({'success': True, 'snapshots_created': count})


class AdminClawbackListView(APIView):
    """
    GET  /api/referral/admin/clawbacks/           — list clawbacks
    POST /api/referral/admin/clawbacks/process-all/ — process all approved
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import CommissionClawback

        status_filter = request.query_params.get('status', 'pending')
        qs = CommissionClawback.objects.select_related(
            'commission', 'commission__user', 'approved_by'
        ).order_by('-created_at')[:100]

        if status_filter != 'all':
            qs = qs.filter(status=status_filter)

        return Response({
            'clawbacks': [{
                'id': c.id,
                'commission_id': c.commission.id,
                'user': c.commission.user.username,
                'clawback_amount': float(c.clawback_amount),
                'reason': c.reason,
                'reason_detail': c.reason_detail,
                'status': c.status,
                'approved_by': (
                    c.approved_by.username if c.approved_by else None
                ),
                'clawed_back_at': (
                    c.clawed_back_at.strftime('%Y-%m-%d %H:%M')
                    if c.clawed_back_at else None
                ),
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
            } for c in qs],
        })


class AdminClawbackActionView(APIView):
    """
    POST /api/referral/admin/clawbacks/<id>/approve/
    POST /api/referral/admin/clawbacks/<id>/reject/
    POST /api/referral/admin/clawbacks/<id>/process/
    """
    permission_classes = [IsAdminUser]

    def post(self, request, clawback_id, action):
        from api.referral.services.CommissionClawbackService import (
            CommissionClawbackService,
        )

        if action == 'approve':
            result = CommissionClawbackService.approve_clawback(
                clawback_id=clawback_id, admin_user=request.user
            )
        elif action == 'reject':
            result = CommissionClawbackService.reject_clawback(
                clawback_id=clawback_id, admin_user=request.user
            )
        elif action == 'process':
            result = CommissionClawbackService.process_approved_clawback(
                clawback_id=clawback_id
            )
        else:
            return Response({'error': 'Invalid action'}, status=400)

        if result.get('success'):
            return Response(result)
        return Response(result, status=400)


class AdminProcessAllClawbacksView(APIView):
    """POST /api/referral/admin/clawbacks/process-all/"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.CommissionClawbackService import (
            CommissionClawbackService,
        )

        dry_run = request.data.get('dry_run', False)
        result = CommissionClawbackService.process_all_approved(
            dry_run=dry_run
        )
        return Response({'success': True, **result})


class AdminMilestoneProgressView(APIView):
    """
    GET /api/referral/admin/milestones/?user_id=123
    Admin: check a user's milestone progress।
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralBonusService import (
            ReferralBonusService,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user_id = request.query_params.get('user_id')
        campaign_id = request.query_params.get('campaign_id')

        if not user_id:
            return Response({'error': 'user_id required'}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        data = ReferralBonusService.get_milestone_progress(
            user=user,
            campaign_id=int(campaign_id) if campaign_id else None,
        )
        return Response({'success': True, **data})


# ─── Export Views ──────────────────────────────────────────────

class AdminExportReferralsView(APIView):
    """GET /api/referral/admin/export/referrals/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralExportService import (
            ReferralExportService,
        )

        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')
        include_suspicious = (
            request.query_params.get('include_suspicious', 'true').lower() == 'true'
        )

        csv_data = ReferralExportService.export_referrals_csv(
            date_from=date_from,
            date_to=date_to,
            include_suspicious=include_suspicious,
        )

        filename = ReferralExportService.get_filename('referrals')
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AdminExportEarningsView(APIView):
    """GET /api/referral/admin/export/earnings/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralExportService import (
            ReferralExportService,
        )

        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')
        level = request.query_params.get('level')

        csv_data = ReferralExportService.export_earnings_csv(
            date_from=date_from,
            date_to=date_to,
            level=int(level) if level else None,
        )

        filename = ReferralExportService.get_filename('earnings')
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AdminExportFraudView(APIView):
    """GET /api/referral/admin/export/fraud/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralExportService import (
            ReferralExportService,
        )

        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')

        csv_data = ReferralExportService.export_fraud_log_csv(
            date_from=date_from, date_to=date_to
        )

        filename = ReferralExportService.get_filename('fraud_log')
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AdminExportTopReferrersView(APIView):
    """GET /api/referral/admin/export/top-referrers/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralExportService import (
            ReferralExportService,
        )

        limit = min(1000, int(request.query_params.get('limit', 100)))
        csv_data = ReferralExportService.export_top_referrers_csv(limit=limit)

        filename = ReferralExportService.get_filename('top_referrers')
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class MyExportLTVView(APIView):
    """GET /api/referral/export/ltv/ — user export their own LTV data"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralExportService import (
            ReferralExportService,
        )

        csv_data = ReferralExportService.export_ltv_report_csv(
            referrer=request.user
        )
        filename = ReferralExportService.get_filename('ltv', request.user.username)
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response