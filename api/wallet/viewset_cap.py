# api/wallet/viewset_cap.py
"""
CPAlead-specific ViewSets (CAP = CPAlead Publisher).
Registered in urls.py alongside main viewsets.
"""
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger("wallet.viewset_cap")


class PublisherDashboardViewSet(viewsets.ViewSet):
    """
    GET /api/wallet/publisher/dashboard/    — full publisher summary
    GET /api/wallet/publisher/earnings/     — earning breakdown
    GET /api/wallet/publisher/level/        — publisher level + upgrade eligibility
    POST /api/wallet/publisher/redeem_points/ — redeem points for BDT
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        try:
            from .services.cpalead.CPALeadService import CPALeadService
            from .services.core.WalletService import WalletService
            wallet  = WalletService.get_or_create(request.user)
            summary = WalletService.get_summary(request.user)

            from .models_cpalead_extra import PublisherLevel, PointsLedger, PayoutSchedule
            level_obj = PublisherLevel.objects.filter(wallet=wallet).first()
            points_obj = PointsLedger.objects.filter(wallet=wallet).first()
            payout_obj = PayoutSchedule.objects.filter(wallet=wallet).first()

            return Response({"success": True, "data": {
                "wallet_summary":    summary,
                "publisher_level":   level_obj.level if level_obj else 1,
                "payout_frequency":  payout_obj.frequency if payout_obj else "net30",
                "points_total":      points_obj.total_points if points_obj else 0,
                "points_tier":       points_obj.current_tier if points_obj else "Starter",
                "can_upgrade":       level_obj.can_upgrade() if level_obj else False,
                "geo_rates": {
                    "US": "2.50×", "GB": "2.50×", "CA": "2.50×",
                    "DE": "1.50×", "BD": "1.00×",
                },
            }})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["get"])
    def level(self, request):
        try:
            from .models_cpalead_extra import PublisherLevel
            from .services.core.WalletService import WalletService
            wallet = WalletService.get_or_create(request.user)
            pl, _ = PublisherLevel.objects.get_or_create(user=request.user, wallet=wallet)
            return Response({"success": True, "data": {
                "level": pl.level, "quality_score": float(pl.quality_score),
                "total_earnings": float(pl.total_earnings),
                "payout_freq": pl.payout_freq, "can_upgrade": pl.can_upgrade(),
                "fraud_flags": pl.fraud_flags,
            }})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)

    @action(detail=False, methods=["post"])
    def redeem_points(self, request):
        try:
            from .models_cpalead_extra import PointsLedger
            from .services.core.WalletService import WalletService
            from .constants import POINTS_PER_DOLLAR
            from decimal import Decimal

            wallet  = WalletService.get_or_create(request.user)
            points  = int(request.data.get("points", 0))
            pl      = PointsLedger.objects.get(wallet=wallet)

            if points < 1000:
                return Response({"success": False, "error": "Minimum 1000 points to redeem"}, status=400)
            if pl.total_points < points:
                return Response({"success": False, "error": "Insufficient points"}, status=400)

            bdt_amount = Decimal(str(points)) / POINTS_PER_DOLLAR * 100  # 1000pts = 1 BDT
            pl.total_points    -= points
            pl.redeemed_points += points
            pl.save(update_fields=["total_points","redeemed_points"])

            WalletService.credit(wallet, bdt_amount, txn_type="bonus", description=f"Points redemption: {points}pts")
            return Response({"success": True, "redeemed_points": points, "credited_bdt": float(bdt_amount)})
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)
