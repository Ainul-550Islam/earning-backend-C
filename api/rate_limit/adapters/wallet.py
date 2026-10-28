# api/rate_limit/adapters/wallet.py
"""
Wallet System ↔ Rate Limit Adapter
=====================================
Covers: withdrawal, earning, transfer, payment request, balance check.

Usage in api/wallet/viewsets/:
    from api.rate_limit.adapters.wallet import WalletRateLimitAdapter

    class WithdrawalViewSet(viewsets.ModelViewSet):
        def create(self, request, *args, **kwargs):
            WalletRateLimitAdapter.check_withdrawal(request).raise_if_blocked()
            ...

Usage in api/wallet/mixins.py → RateLimitMixin:
    Replace internal WalletRateLimiter with this adapter.
"""

import logging
from decimal import Decimal
from typing import Optional

from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.wallet')


class WalletRateLimitAdapter:
    """Adapter for api/wallet system."""

    # ── Withdrawal ─────────────────────────────────────────────

    @staticmethod
    def check_withdrawal(request, amount: Optional[Decimal] = None) -> RateLimitResult:
        """
        Check before any withdrawal request.
        Critical — limits per user per day.

        Where to call:
            api/wallet/viewsets/ → WithdrawalViewSet.create()
            api/wallet/services/withdrawal/ → WithdrawalService.process()
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'wallet_withdrawal',
            request=request,
            user=user,
            extra_context={
                'amount': str(amount) if amount else '',
                'endpoint': 'withdrawal',
            },
        )

    # ── Payment Request ────────────────────────────────────────

    @staticmethod
    def check_payment_request(request) -> RateLimitResult:
        """
        Check before creating a payment request.

        Where to call:
            api/wallet/viewsets/ → PaymentRequestViewSet.create()
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'wallet_payment_request',
            request=request,
            user=user,
            extra_context={'endpoint': 'payment_request'},
        )

    # ── Earning ────────────────────────────────────────────────

    @staticmethod
    def check_earning(request, task_type: str = '', offer_id: str = '') -> RateLimitResult:
        """
        Check before crediting an earning to the wallet.
        Prevents duplicate/fraudulent earning claims.

        Where to call:
            api/wallet/services/earning/ → EarningService.credit()
            api/wallet/tasks/ → celery earning tasks
        """
        user = getattr(request, 'user', None) if request else None
        return RateLimitIntegrationService.check(
            'wallet_earning',
            request=request,
            user=user,
            extra_context={
                'task_type': task_type,
                'offer_id': offer_id,
            },
        )

    @staticmethod
    def check_earning_by_user(user, task_type: str = '', offer_id: str = '') -> RateLimitResult:
        """
        Earning check without a request object.
        Used in Celery tasks / background jobs.

        Where to call:
            api/wallet/tasks/ → process_earning_task()
        """
        return RateLimitIntegrationService.check(
            'wallet_earning',
            user=user,
            extra_context={
                'task_type': task_type,
                'offer_id': offer_id,
                'source': 'celery_task',
            },
        )

    # ── Transfer ───────────────────────────────────────────────

    @staticmethod
    def check_transfer(request, to_user_id: int = 0) -> RateLimitResult:
        """
        Check before wallet-to-wallet transfer.

        Where to call:
            api/wallet/viewsets/ → TransferViewSet.create()
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'wallet_transfer',
            request=request,
            user=user,
            extra_context={'to_user_id': to_user_id},
        )

    # ── Balance Check ──────────────────────────────────────────

    @staticmethod
    def check_balance_check(request) -> RateLimitResult:
        """
        Check before balance queries (prevent scraping).

        Where to call:
            api/wallet/viewsets/ → WalletViewSet.retrieve()
        """
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'wallet_balance_check',
            request=request,
            user=user,
        )

    # ── Premium status sync ─────────────────────────────────────

    @staticmethod
    def notify_premium_activated(user) -> bool:
        """
        Call when user purchases premium subscription.
        Upgrades their rate limit tier.

        Where to call:
            api/wallet/services/billing/ → after successful premium purchase
            api/subscription/ → on subscription activation
        """
        return RateLimitIntegrationService.set_premium(user, is_premium=True)

    @staticmethod
    def notify_premium_cancelled(user) -> bool:
        """
        Call when premium is cancelled/expired.

        Where to call:
            api/wallet/services/billing/ → subscription cancellation
        """
        return RateLimitIntegrationService.set_premium(user, is_premium=False)

    # ── Mixin replacement ──────────────────────────────────────

    @staticmethod
    def check_from_mixin(user_id: int, action: str = 'api_global') -> RateLimitResult:
        """
        Drop-in replacement for api/wallet/mixins.py → RateLimitMixin.
        Replace:
            from .rate_limiter import WalletRateLimiter
            allowed, remaining, _ = WalletRateLimiter.check(user_id, action)
        With:
            from api.rate_limit.adapters.wallet import WalletRateLimitAdapter
            result = WalletRateLimitAdapter.check_from_mixin(user_id, action)
            if not result.allowed: raise Throttled(...)
        """
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=user_id).first()
        except Exception:
            user = None

        return RateLimitIntegrationService.check(
            action,
            user=user,
            extra_context={'source': 'wallet_mixin'},
        )
