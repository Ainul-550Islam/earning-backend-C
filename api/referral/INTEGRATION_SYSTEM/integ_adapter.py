# api/referral/INTEGRATION_SYSTEM/integ_adapter.py
# Adapters — thin wrappers around external module APIs
# Referral code never calls external modules directly — always through adapters
# ============================================================

import logging
from decimal import Decimal
from typing import Optional, Any
from .integ_exceptions import ModuleUnavailableError, AdapterError

logger = logging.getLogger(__name__)


# ── Wallet Adapter ────────────────────────────────────────────────────────────

class WalletAdapter:
    """
    Wraps api/wallet/services.py → WalletService
    All referral wallet operations go through here.
    """

    @staticmethod
    def get_or_create_wallet(user):
        """Get or create user wallet."""
        try:
            from api.wallet.models import Wallet
            wallet, _ = Wallet.objects.get_or_create(user=user)
            return wallet
        except ImportError:
            raise ModuleUnavailableError('wallet', 'Wallet model not found')

    @staticmethod
    def credit_referral_commission(
        user,
        amount: Decimal,
        level: int,
        referred_user_id: int,
        source_id: str = '',
    ) -> Optional[Any]:
        """
        Credit referral commission to user wallet.
        Uses WalletService.add_referral_commission() (project's native method).
        """
        try:
            from api.wallet.services import WalletService
            wallet = WalletAdapter.get_or_create_wallet(user)
            return WalletService.add_referral_commission(
                wallet=wallet,
                amount=amount,
                level=level,
                referred_user_id=referred_user_id,
                source_task_id=source_id,
                source_earning_id=source_id,
            )
        except ImportError:
            raise ModuleUnavailableError('wallet', 'WalletService not found')
        except Exception as e:
            logger.error(f'[WalletAdapter] credit_referral_commission error: {e}')
            raise AdapterError(f'Wallet credit failed: {e}') from e

    @staticmethod
    def credit_bonus(user, amount: Decimal, description: str) -> Optional[Any]:
        """Credit signup/milestone bonus."""
        try:
            from api.wallet.services import WalletService
            wallet = WalletAdapter.get_or_create_wallet(user)
            return WalletService.add_earnings(
                wallet=wallet,
                amount=amount,
                description=description,
                source_type='referral',
                source_id='bonus',
            )
        except ImportError:
            raise ModuleUnavailableError('wallet', 'WalletService not found')
        except Exception as e:
            raise AdapterError(f'Wallet bonus failed: {e}') from e

    @staticmethod
    def deduct_clawback(user, amount: Decimal, clawback_id: int) -> Optional[Any]:
        """Deduct clawback amount from wallet."""
        try:
            from api.wallet.services import WalletService
            wallet = WalletAdapter.get_or_create_wallet(user)
            # Use add_earnings with negative amount for deduction
            return WalletService.add_earnings(
                wallet=wallet,
                amount=-abs(amount),
                description=f'Referral commission clawback #{clawback_id}',
                source_type='referral_clawback',
                source_id=str(clawback_id),
            )
        except Exception as e:
            raise AdapterError(f'Wallet clawback deduct failed: {e}') from e


# ── Notification Adapter ──────────────────────────────────────────────────────

class NotificationAdapter:
    """
    Wraps api/notifications/services.py → NotificationService
    """

    _service = None

    @classmethod
    def _get_service(cls):
        if cls._service is None:
            try:
                from api.notifications.services import NotificationService
                cls._service = NotificationService()
            except ImportError:
                raise ModuleUnavailableError('notifications', 'NotificationService not found')
        return cls._service

    @staticmethod
    def send(
        user,
        title: str,
        message: str,
        notification_type: str = 'referral_commission',
        priority: str = 'medium',
        channel: str = 'in_app',
    ) -> bool:
        """Send a notification to user."""
        try:
            ns = NotificationAdapter._get_service()
            ns.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                channel=channel,
            )
            return True
        except ModuleUnavailableError:
            logger.debug('[NotifAdapter] Notification module unavailable')
            return False
        except Exception as e:
            logger.warning(f'[NotifAdapter] send failed: {e}')
            return False

    @staticmethod
    def send_bulk(users, title: str, message: str, notification_type: str = 'general') -> int:
        """Send notification to multiple users."""
        sent = 0
        for user in users:
            if NotificationAdapter.send(user, title, message, notification_type):
                sent += 1
        return sent


# ── Fraud Detection Adapter ───────────────────────────────────────────────────

class FraudAdapter:
    """
    Wraps api/fraud_detection → FraudScoreCalculator
    Referral fraud check can optionally use project-wide fraud scoring.
    """

    @staticmethod
    def get_user_risk_score(user) -> Optional[float]:
        """Get project-wide fraud risk score for a user."""
        try:
            from api.fraud_detection.services.FraudScoreCalculator import (
                FraudScoreCalculator
            )
            calc = FraudScoreCalculator()
            breakdown = calc.calculate_risk_breakdown(user)
            return breakdown.get('overall_risk', 0)
        except ImportError:
            return None
        except Exception as e:
            logger.debug(f'[FraudAdapter] get_user_risk_score failed: {e}')
            return None

    @staticmethod
    def is_high_risk_user(user, threshold: float = 0.7) -> bool:
        """Check if user is high fraud risk."""
        score = FraudAdapter.get_user_risk_score(user)
        if score is None:
            return False
        return score >= threshold


# ── Analytics Adapter ─────────────────────────────────────────────────────────

class AnalyticsAdapter:
    """
    Wraps api/analytics → AnalyticsEvent
    """

    @staticmethod
    def track_event(event_type: str, user, metadata: dict = None) -> bool:
        """Track an analytics event."""
        try:
            from api.analytics.models import AnalyticsEvent
            AnalyticsEvent.objects.create(
                event_type=event_type,
                user=user,
                metadata=metadata or {},
            )
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f'[AnalyticsAdapter] track_event failed: {e}')
            return False

    @staticmethod
    def track_referral_created(referrer, referred_user) -> None:
        AnalyticsAdapter.track_event(
            'referral_created', referrer,
            {'referred_user_id': referred_user.id}
        )

    @staticmethod
    def track_commission_paid(user, amount: Decimal, level: int) -> None:
        AnalyticsAdapter.track_event(
            'referral_commission', user,
            {'amount': str(amount), 'level': level}
        )


# ── Djoyalty Adapter ──────────────────────────────────────────────────────────

class DjoyaltyAdapter:
    """
    Wraps api/djoyalty → loyalty points for referral actions.
    """

    @staticmethod
    def award_referral_points(referrer, referee) -> bool:
        """Award djoyalty points for referral."""
        try:
            from api.djoyalty.services.earn.ReferralPointsService import (
                ReferralPointsService
            )
            tenant = getattr(referrer, 'tenant', None)
            return ReferralPointsService.process_referral(
                referrer=referrer,
                referee=referee,
                tenant=tenant,
            )
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f'[DjoyaltyAdapter] award_referral_points failed: {e}')
            return False


# ── Rate Limit Adapter ────────────────────────────────────────────────────────

class RateLimitAdapter:
    """
    Wraps api/rate_limit → check referral activity limits.
    """

    @staticmethod
    def check_referral_activity(user, action: str = 'referral') -> bool:
        """
        Check if user is within referral activity rate limits.
        Returns True if allowed, False if rate limited.
        """
        try:
            from api.rate_limit.services.RateLimitService import RateLimitService
            service = RateLimitService()
            result = service.check_referral_activity(user=user)
            return result.get('allowed', True)
        except ImportError:
            return True  # Allow if rate limit module unavailable
        except Exception as e:
            logger.debug(f'[RateLimitAdapter] check failed: {e}')
            return True


# ── Adapter Factory ───────────────────────────────────────────────────────────

class AdapterFactory:
    """
    Central factory for all adapters.
    Use this instead of importing adapters directly.
    """
    _wallet: Optional[WalletAdapter] = None
    _notification: Optional[NotificationAdapter] = None
    _fraud: Optional[FraudAdapter] = None
    _analytics: Optional[AnalyticsAdapter] = None
    _djoyalty: Optional[DjoyaltyAdapter] = None
    _rate_limit: Optional[RateLimitAdapter] = None

    @classmethod
    def wallet(cls) -> WalletAdapter:
        if cls._wallet is None:
            cls._wallet = WalletAdapter()
        return cls._wallet

    @classmethod
    def notification(cls) -> NotificationAdapter:
        if cls._notification is None:
            cls._notification = NotificationAdapter()
        return cls._notification

    @classmethod
    def fraud(cls) -> FraudAdapter:
        if cls._fraud is None:
            cls._fraud = FraudAdapter()
        return cls._fraud

    @classmethod
    def analytics(cls) -> AnalyticsAdapter:
        if cls._analytics is None:
            cls._analytics = AnalyticsAdapter()
        return cls._analytics

    @classmethod
    def djoyalty(cls) -> DjoyaltyAdapter:
        if cls._djoyalty is None:
            cls._djoyalty = DjoyaltyAdapter()
        return cls._djoyalty

    @classmethod
    def rate_limit(cls) -> RateLimitAdapter:
        if cls._rate_limit is None:
            cls._rate_limit = RateLimitAdapter()
        return cls._rate_limit