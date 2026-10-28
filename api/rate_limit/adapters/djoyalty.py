# api/rate_limit/adapters/djoyalty.py
"""
Djoyalty (Loyalty System) ↔ Rate Limit Adapter
=================================================
Covers: points earn, redemption, tier upgrade, campaign, 
        voucher, gift card, leaderboard, streak, badge.

Usage in api/djoyalty/viewsets/points/PointsViewSet.py:
    from api.rate_limit.adapters.djoyalty import DjoyaltyRateLimitAdapter

    class PointsViewSet(viewsets.ModelViewSet):
        def create(self, request, *args, **kwargs):
            DjoyaltyRateLimitAdapter.check_earn_points(request).raise_if_blocked()
            ...

Usage in api/djoyalty/services/redemption/RedemptionService.py:
    DjoyaltyRateLimitAdapter.check_redemption(user=user).raise_if_blocked()

Usage in api/djoyalty/services/points/WalletBridgeService.py:
    DjoyaltyRateLimitAdapter.check_wallet_bridge(user=user).raise_if_blocked()
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.djoyalty')


class DjoyaltyRateLimitAdapter:
    """Adapter for api/djoyalty loyalty system."""

    # ── Points Earn ────────────────────────────────────────────

    @staticmethod
    def check_earn_points(request=None, user=None, earn_type: str = '') -> RateLimitResult:
        """
        Check before awarding loyalty points.
        Prevents rapid point farming.

        Where to call:
            api/djoyalty/viewsets/points/PointsViewSet.py → create()
            api/djoyalty/services/earn/EarnRuleEngine.py → evaluate()
            api/djoyalty/services/earn/BonusEventService.py → award()
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_earn_points',
            request=request, user=user,
            extra_context={'earn_type': earn_type},
        )

    # ── Redemption ─────────────────────────────────────────────

    @staticmethod
    def check_redemption(request=None, user=None, reward_type: str = '') -> RateLimitResult:
        """
        Check before redeeming loyalty points.

        Where to call:
            api/djoyalty/viewsets/redemption/RedemptionViewSet.py → create()
            api/djoyalty/services/redemption/RedemptionService.py → redeem()
            api/djoyalty/services/redemption/RedemptionApprovalService.py
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_redemption',
            request=request, user=user,
            extra_context={'reward_type': reward_type},
        )

    # ── Voucher ────────────────────────────────────────────────

    @staticmethod
    def check_voucher_use(request=None, user=None, voucher_code: str = '') -> RateLimitResult:
        """
        Check before applying a voucher.

        Where to call:
            api/djoyalty/viewsets/redemption/VoucherViewSet.py → apply action
            api/djoyalty/services/redemption/VoucherService.py → apply()
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_voucher_use',
            request=request, user=user,
            extra_context={'voucher_code': voucher_code},
        )

    # ── Gift Card ──────────────────────────────────────────────

    @staticmethod
    def check_gift_card_redeem(request=None, user=None) -> RateLimitResult:
        """
        Check before redeeming a gift card.

        Where to call:
            api/djoyalty/viewsets/redemption/GiftCardViewSet.py → redeem action
            api/djoyalty/services/redemption/GiftCardService.py → redeem()
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_gift_card',
            request=request, user=user,
        )

    # ── Transfer ───────────────────────────────────────────────

    @staticmethod
    def check_points_transfer(request=None, user=None, to_user_id: int = 0) -> RateLimitResult:
        """
        Check before transferring points to another user.

        Where to call:
            api/djoyalty/viewsets/points/PointsTransferViewSet.py → create()
            api/djoyalty/services/points/PointsTransferService.py → transfer()
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_points_transfer',
            request=request, user=user,
            extra_context={'to_user_id': to_user_id},
        )

    # ── Wallet Bridge ──────────────────────────────────────────

    @staticmethod
    def check_wallet_bridge(request=None, user=None, amount=None) -> RateLimitResult:
        """
        Check before converting loyalty points to wallet balance.
        Critical — bridges djoyalty and wallet systems.

        Where to call:
            api/djoyalty/services/points/WalletBridgeService.py → convert()
            api/djoyalty/viewsets/points/PointsConversionViewSet.py → create()
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_wallet_bridge',
            request=request, user=user,
            extra_context={'amount': str(amount) if amount else ''},
        )

    # ── Campaign ───────────────────────────────────────────────

    @staticmethod
    def check_campaign_participate(request=None, user=None, campaign_id=None) -> RateLimitResult:
        """
        Check before participating in a campaign.

        Where to call:
            api/djoyalty/viewsets/advanced/CampaignViewSet.py → participate action
            api/djoyalty/services/advanced/CampaignService.py → add_participant()
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'djoyalty_campaign',
            request=request, user=user,
            extra_context={'campaign_id': str(campaign_id) if campaign_id else ''},
        )

    # ── Fraud sync ─────────────────────────────────────────────

    @staticmethod
    def report_loyalty_fraud(user=None, ip_address: str = '', risk_score: int = 0) -> dict:
        """
        Report loyalty fraud signal to rate_limit system.

        Where to call:
            api/djoyalty/services/advanced/LoyaltyFraudService.py → report()
            api/djoyalty/tasks/fraud_check_tasks.py
        """
        return RateLimitIntegrationService.sync_fraud_signal(
            user=user,
            ip_address=ip_address,
            risk_score=risk_score,
            fraud_type='loyalty_fraud',
            auto_block=(risk_score >= 90),
        )

    # ── Tier upgrade ───────────────────────────────────────────

    @staticmethod
    def on_tier_upgrade(user, new_tier: str = '') -> bool:
        """
        When user upgrades tier, increase their rate limit.

        Where to call:
            api/djoyalty/services/tiers/TierUpgradeService.py → upgrade()
            api/djoyalty/signals/tier_signals.py
        """
        # Gold/Platinum tiers get premium limits
        is_premium = new_tier.lower() in ('gold', 'platinum', 'diamond', 'vip')
        return RateLimitIntegrationService.set_premium(user, is_premium=is_premium)
