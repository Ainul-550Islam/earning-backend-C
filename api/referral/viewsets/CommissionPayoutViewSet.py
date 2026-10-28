# api/referral/viewsets/CommissionPayoutViewSet.py
# Commission payout: list, create, admin process
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class CommissionPayoutViewSet(APIView):
    """
    GET  /api/referral/payouts/        — my payout history
    POST /api/referral/payouts/create/ — create payout request
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.models import CommissionPayout

        payouts = CommissionPayout.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]

        return Response({
            'success': True,
            'payouts': [{
                'id': p.id,
                'total_amount': float(p.total_amount),
                'period': p.period,
                'status': p.status,
                'paid_at': (
                    p.paid_at.strftime('%Y-%m-%d %H:%M')
                    if p.paid_at else None
                ),
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M'),
            } for p in payouts],
        })

    def post(self, request):
        from api.referral.services.CommissionService import CommissionService

        period = request.data.get('period', 'manual')
        result = CommissionService.create_payout(
            user=request.user, period=period
        )
        if result.get('success'):
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class AdminPayoutProcessView(APIView):
    """
    POST /api/referral/admin/payouts/<payout_id>/process/
    Admin: process a pending payout।
    """
    permission_classes = [IsAdminUser]

    def post(self, request, payout_id):
        from api.referral.models import CommissionPayout
        from api.wallet.services import WalletService
        from api.wallet.models import Wallet

        try:
            payout = CommissionPayout.objects.select_related('user').get(
                id=payout_id, status='pending'
            )
        except CommissionPayout.DoesNotExist:
            return Response({'error': 'Payout not found or not pending'}, status=404)

        try:
            wallet, _ = Wallet.objects.get_or_create(user=payout.user)
            wallet_txn = WalletService.add_earnings(
                wallet=wallet,
                amount=payout.total_amount,
                description=f"Referral commission payout [{payout.period}]",
                source_type='commission_payout',
                source_id=str(payout.id),
            )
            payout.mark_completed(
                wallet_txn_id=str(
                    getattr(wallet_txn, 'walletTransaction_id', '')
                )
            )
            payout.processed_by = request.user
            payout.save(update_fields=['processed_by'])

            return Response({
                'success': True,
                'payout_id': payout.id,
                'amount': float(payout.total_amount),
                'user': payout.user.username,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AdminPayoutListView(APIView):
    """
    GET /api/referral/admin/payouts/
    Admin: all payouts with filtering।
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import CommissionPayout

        status_filter = request.query_params.get('status')
        qs = CommissionPayout.objects.select_related('user').order_by(
            '-created_at'
        )[:100]

        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response({
            'payouts': [{
                'id': p.id,
                'user': p.user.username,
                'total_amount': float(p.total_amount),
                'period': p.period,
                'status': p.status,
                'paid_at': (
                    p.paid_at.strftime('%Y-%m-%d %H:%M')
                    if p.paid_at else None
                ),
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M'),
            } for p in qs],
        })