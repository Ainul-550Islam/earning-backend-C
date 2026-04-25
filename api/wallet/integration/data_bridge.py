# api/wallet/integration/data_bridge.py
"""
Data bridge — sync wallet with other Django apps.
Connects wallet to: users, tasks, offers, fraud_detection, notifications.

This is the anti-corruption layer between wallet and the rest of the API.
Wallet never imports directly from other apps — always through this bridge.
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("wallet.integration.bridge")


class UserBridge:
    """Bridge to users app."""

    @staticmethod
    def get_user_tier(user) -> str:
        """Get user tier for earn multiplier."""
        try:
            return getattr(user, "tier", "FREE") or "FREE"
        except Exception:
            return "FREE"

    @staticmethod
    def get_user_fcm_token(user_id: int) -> str:
        """Get Firebase FCM token for push notification."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return getattr(user, "fcm_token", "") or ""
        except Exception:
            return ""

    @staticmethod
    def get_user_phone(user_id: int) -> str:
        """Get user phone number for SMS."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return getattr(user, "phone_number", "") or ""
        except Exception:
            return ""

    @staticmethod
    def update_user_stats_on_earn(user_id: int, amount: Decimal):
        """Update UserStatistics when user earns."""
        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.get_or_create(user_id=user_id)
            stats.total_earned  = (stats.total_earned or Decimal("0")) + amount
            stats.earned_today  = (stats.earned_today  or Decimal("0")) + amount
            stats.save(update_fields=["total_earned","earned_today"])
        except Exception as e:
            logger.debug(f"UserStatistics earn update skip: {e}")

    @staticmethod
    def update_user_stats_on_withdraw(user_id: int, amount: Decimal):
        """Update UserStatistics when user withdraws."""
        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.get_or_create(user_id=user_id)
            stats.total_withdrawn   = (stats.total_withdrawn or Decimal("0")) + amount
            stats.withdrawals_count = (stats.withdrawals_count or 0) + 1
            stats.save(update_fields=["total_withdrawn","withdrawals_count"])
        except Exception as e:
            logger.debug(f"UserStatistics withdraw update skip: {e}")

    @staticmethod
    def get_referrer(user_id: int) -> Optional[int]:
        """Get the referrer user_id for a user."""
        try:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(id=user_id)
            return getattr(user, "referred_by_id", None)
        except Exception:
            return None


class FraudBridge:
    """Bridge to fraud_detection app."""

    @staticmethod
    def get_risk_score(user_id: int) -> float:
        """Get ML risk score from fraud detection app."""
        try:
            from api.fraud_detection.models import UserRiskProfile
            risk = UserRiskProfile.objects.filter(user_id=user_id).first()
            return float(getattr(risk, "overall_risk_score", 0) or 0)
        except Exception:
            return 0.0

    @staticmethod
    def is_user_restricted(user_id: int) -> bool:
        """Check if fraud detection has restricted user."""
        try:
            from api.fraud_detection.models import UserRiskProfile
            risk = UserRiskProfile.objects.filter(user_id=user_id).first()
            return bool(getattr(risk, "is_restricted", False))
        except Exception:
            return False

    @staticmethod
    def report_suspicious_transaction(user_id: int, wallet_id: int,
                                      amount: Decimal, txn_type: str, signals: list):
        """Report suspicious transaction to fraud detection."""
        try:
            from api.fraud_detection.services import FraudService
            FraudService.flag_transaction(
                user_id=user_id, amount=float(amount),
                txn_type=txn_type, signals=signals,
            )
        except Exception as e:
            logger.debug(f"Fraud report skip: {e}")


class TaskBridge:
    """Bridge to tasks/offers app."""

    @staticmethod
    def get_task_payout(task_id: int) -> Decimal:
        """Get payout amount for a completed task."""
        try:
            from api.tasks.models import Task
            task = Task.objects.get(id=task_id)
            return getattr(task, "reward_amount", Decimal("0")) or Decimal("0")
        except Exception:
            return Decimal("0")

    @staticmethod
    def mark_task_paid(task_completion_id: int):
        """Mark task completion as paid."""
        try:
            from api.tasks.models import TaskCompletion
            tc = TaskCompletion.objects.get(id=task_completion_id)
            tc.is_paid = True
            tc.save(update_fields=["is_paid"])
        except Exception as e:
            logger.debug(f"Mark task paid skip: {e}")


class NotificationBridge:
    """Bridge to notification system."""

    @staticmethod
    def send(user_id: int, event_type: str, data: dict):
        """Send notification via wallet notifier."""
        try:
            from ..notifications import WalletNotifier
            WalletNotifier.send(user_id=user_id, event_type=event_type, data=data)
        except Exception as e:
            logger.debug(f"Notification send skip: {e}")
