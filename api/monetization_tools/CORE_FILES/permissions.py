"""CORE_FILES/permissions.py — Re-exports all DRF permissions."""
from ..permissions import (
    IsOwnerOrAdmin, IsAdminOrReadOnly, IsVerifiedUser, IsTenantMember,
    CanAccessOfferwall, CanManageCampaign, CanManageSubscription,
    CanManagePublisherAccount, CanViewAnalytics, CanManageFraudAlerts,
    CanManagePayouts, CanManageReferrals, CanManageFlashSales,
    CanManageCoupons, IsAccountActive, CanManagePostbacks, CanManageSegments,
)
