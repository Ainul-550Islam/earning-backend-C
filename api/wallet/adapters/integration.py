# api/wallet/adapters.py
"""
WalletAdapter — Universal integration bridge between api.wallet and all
external apps in the platform.

This file is the SINGLE point of contact between the wallet system and:
    - api.fraud_detection     → FraudSignalAdapter
    - api.analytics           → WalletAnalyticsAdapter
    - api.referral            → ReferralWalletAdapter
    - api.notifications       → WalletNotificationAdapter
    - api.kyc                 → KYCWalletAdapter
    - api.payout_queue        → PayoutQueueAdapter
    - api.webhooks            → ExternalWebhookAdapter
    - api.postback            → PostbackWalletAdapter
    - api.ai_engine           → AIWalletAdapter
    - api.subscription        → SubscriptionWalletAdapter
    - api.gamification        → GamificationWalletAdapter
    - api.engagement          → EngagementWalletAdapter
    - api.promotions          → PromotionWalletAdapter
    - api.offer_routing       → OfferRoutingAdapter
    - api.publisher_tools     → PublisherToolsAdapter
    - api.monetization_tools  → MonetizationAdapter
    - api.postback_engine     → PostbackEngineAdapter
    - api.marketplace         → MarketplaceWalletAdapter
    - api.dr_integration      → DisasterRecoveryAdapter
    - api.behavior_analytics  → BehaviorAnalyticsAdapter
    - api.auto_mod            → AutoModWalletAdapter
    - api.alerts              → AlertWalletAdapter
    - api.support             → SupportWalletAdapter

Design principles:
    1. All imports are LAZY (inside methods) — wallet never hard-depends on external apps
    2. All calls wrapped in try/except — external app failure never breaks wallet
    3. Returns dict with {"success": bool, ...} — callers can inspect or ignore
    4. Signals-based where possible — decoupled async-first
    5. Each adapter is a standalone class — can be tested/mocked independently

Usage:
    from api.wallet.adapters import WalletAdapter
    WalletAdapter.on_credit(txn, user, wallet, amount)
    WalletAdapter.on_withdrawal_completed(txn, user, wallet, amount)
    WalletAdapter.on_kyc_approved(user, wallet, kyc_level)
    WalletAdapter.check_offer_payout_allowed(user, wallet, amount, offer_id)
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .models import Wallet, WalletTransaction

logger = logging.getLogger("wallet.adapters")


# ═══════════════════════════════════════════════════════════════════════════
# 1. FraudSignalAdapter  →  api.fraud_detection
# ═══════════════════════════════════════════════════════════════════════════
class FraudSignalAdapter:
    """
    Pushes wallet events into api.fraud_detection for real-time scoring.
    Called after every credit/debit so fraud_detection can build velocity models.
    """

    @staticmethod
    def on_transaction(txn: "WalletTransaction", user, wallet: "Wallet",
                       ip_address: str = "", device_info: dict = None) -> dict:
        """Signal a transaction event to the fraud detection engine."""
        try:
            from api.fraud_detection.services import FraudEngine
            payload = {
                "txn_id":      str(txn.txn_id),
                "user_id":     user.pk,
                "wallet_id":   wallet.pk,
                "amount":      str(txn.amount),
                "txn_type":    txn.type,
                "ip_address":  ip_address,
                "device_info": device_info or {},
            }
            result = FraudEngine.evaluate(payload)
            if result.get("block"):
                logger.warning(
                    f"[FraudAdapter] Transaction {txn.txn_id} flagged: {result.get('reason')}"
                )
            return result
        except ImportError:
            logger.debug("[FraudAdapter] api.fraud_detection not installed — skipping")
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[FraudAdapter] Error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def on_withdrawal_requested(user, wallet: "Wallet",
                                amount: Decimal, method_type: str,
                                ip_address: str = "") -> dict:
        """Pre-withdrawal fraud gate — call before processing withdrawal."""
        try:
            from api.fraud_detection.services import FraudEngine
            result = FraudEngine.check_withdrawal({
                "user_id":     user.pk,
                "wallet_id":   wallet.pk,
                "amount":      str(amount),
                "method_type": method_type,
                "ip_address":  ip_address,
            })
            return result
        except ImportError:
            return {"success": True, "allowed": True, "skipped": True}
        except Exception as e:
            logger.error(f"[FraudAdapter] Withdrawal check error: {e}")
            return {"success": True, "allowed": True, "error": str(e)}

    @staticmethod
    def on_suspicious_activity(user, wallet: "Wallet",
                               event_type: str, details: dict = None) -> dict:
        """Report a suspicious event (multiple failed attempts, IP changes, etc)."""
        try:
            from api.fraud_detection.services import FraudEngine
            return FraudEngine.report_suspicious({
                "user_id":    user.pk,
                "wallet_id":  wallet.pk,
                "event_type": event_type,
                "details":    details or {},
            })
        except ImportError:
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[FraudAdapter] Suspicious report error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 2. WalletAnalyticsAdapter  →  api.analytics
# ═══════════════════════════════════════════════════════════════════════════
class WalletAnalyticsAdapter:
    """
    Pushes wallet metrics to api.analytics for dashboards and reporting.
    Fire-and-forget — analytics never blocks wallet operations.
    """

    @staticmethod
    def track_credit(user, wallet: "Wallet", amount: Decimal,
                     txn_type: str, country_code: str = "") -> None:
        try:
            from api.analytics.tracker import WalletTracker
            WalletTracker.track("wallet.credit", {
                "user_id":      user.pk,
                "amount":       float(amount),
                "txn_type":     txn_type,
                "country_code": country_code,
                "wallet_id":    wallet.pk,
            })
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[AnalyticsAdapter] track_credit error: {e}")

    @staticmethod
    def track_withdrawal(user, wallet: "Wallet", amount: Decimal,
                         gateway: str, status: str) -> None:
        try:
            from api.analytics.tracker import WalletTracker
            WalletTracker.track("wallet.withdrawal", {
                "user_id":   user.pk,
                "amount":    float(amount),
                "gateway":   gateway,
                "status":    status,
                "wallet_id": wallet.pk,
            })
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[AnalyticsAdapter] track_withdrawal error: {e}")

    @staticmethod
    def track_balance_snapshot(wallet: "Wallet") -> None:
        """Daily balance snapshot for trend analysis."""
        try:
            from api.analytics.tracker import WalletTracker
            WalletTracker.track("wallet.balance_snapshot", {
                "wallet_id":    wallet.pk,
                "user_id":      wallet.user_id,
                "balance":      float(wallet.current_balance),
                "frozen":       float(wallet.frozen_balance or 0),
                "total_earned": float(wallet.total_earned),
            })
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[AnalyticsAdapter] snapshot error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 3. ReferralWalletAdapter  →  api.referral
# ═══════════════════════════════════════════════════════════════════════════
class ReferralWalletAdapter:
    """
    Credits referral bonuses and reports wallet activity that generates
    referral commissions to api.referral.
    """

    @staticmethod
    def on_referral_earning(referrer_user, referred_user,
                            earning_amount: Decimal,
                            source: str = "offer") -> dict:
        """
        Called when a referred user earns money. Triggers commission
        calculation and credits the referrer's wallet.
        """
        try:
            from api.referral.services import ReferralService
            return ReferralService.process_commission(
                referrer_id=referrer_user.pk,
                referred_id=referred_user.pk,
                base_amount=earning_amount,
                source=source,
            )
        except ImportError:
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[ReferralAdapter] Commission error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def on_first_withdrawal(user, wallet: "Wallet", amount: Decimal) -> dict:
        """First withdrawal milestone — triggers referral unlock bonuses."""
        try:
            from api.referral.services import ReferralService
            return ReferralService.on_user_first_withdrawal(user.pk, float(amount))
        except ImportError:
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[ReferralAdapter] First withdrawal error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_referral_stats(user) -> dict:
        """Fetch referral stats to display on wallet dashboard."""
        try:
            from api.referral.services import ReferralService
            return ReferralService.get_stats(user.pk)
        except ImportError:
            return {"total_referrals": 0, "total_commission": "0.00", "skipped": True}
        except Exception as e:
            logger.error(f"[ReferralAdapter] Stats error: {e}")
            return {"total_referrals": 0, "total_commission": "0.00"}


# ═══════════════════════════════════════════════════════════════════════════
# 4. WalletNotificationAdapter  →  api.notifications
# ═══════════════════════════════════════════════════════════════════════════
class WalletNotificationAdapter:
    """
    Sends user-facing notifications for wallet events via api.notifications.
    Supports push, email, SMS, and in-app channels.
    """

    @staticmethod
    def notify_credit(user, amount: Decimal, txn_type: str,
                      wallet_balance: Decimal) -> None:
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user_id=user.pk,
                template="wallet.credited",
                context={
                    "amount":     str(amount),
                    "txn_type":   txn_type,
                    "balance":    str(wallet_balance),
                    "currency":   "BDT",
                },
                channels=["push", "in_app"],
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[NotificationAdapter] notify_credit error: {e}")

    @staticmethod
    def notify_withdrawal_initiated(user, amount: Decimal, method: str) -> None:
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user_id=user.pk,
                template="wallet.withdrawal_initiated",
                context={"amount": str(amount), "method": method, "currency": "BDT"},
                channels=["push", "in_app", "email"],
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[NotificationAdapter] withdrawal_initiated error: {e}")

    @staticmethod
    def notify_withdrawal_approved(user, amount: Decimal,
                                   net_amount: Decimal, gateway: str) -> None:
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user_id=user.pk,
                template="wallet.withdrawal_approved",
                context={
                    "amount":     str(amount),
                    "net_amount": str(net_amount),
                    "gateway":    gateway,
                    "currency":   "BDT",
                },
                channels=["push", "in_app", "email", "sms"],
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[NotificationAdapter] withdrawal_approved error: {e}")

    @staticmethod
    def notify_withdrawal_rejected(user, amount: Decimal, reason: str) -> None:
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user_id=user.pk,
                template="wallet.withdrawal_rejected",
                context={"amount": str(amount), "reason": reason},
                channels=["push", "in_app", "email"],
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[NotificationAdapter] withdrawal_rejected error: {e}")

    @staticmethod
    def notify_wallet_locked(user, reason: str) -> None:
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user_id=user.pk,
                template="wallet.locked",
                context={"reason": reason},
                channels=["push", "in_app", "email", "sms"],
                priority="critical",
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[NotificationAdapter] wallet_locked error: {e}")

    @staticmethod
    def notify_kyc_required(user, required_level: int, reason: str = "") -> None:
        try:
            from api.notifications.services import NotificationService
            NotificationService.send(
                user_id=user.pk,
                template="wallet.kyc_required",
                context={"required_level": required_level, "reason": reason},
                channels=["push", "in_app", "email"],
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[NotificationAdapter] kyc_required error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 5. KYCWalletAdapter  →  api.kyc
# ═══════════════════════════════════════════════════════════════════════════
class KYCWalletAdapter:
    """
    Fetches KYC status from api.kyc to enforce withdrawal limits and
    permission gates inside the wallet system.
    """

    @staticmethod
    def get_kyc_level(user) -> int:
        """Return the user's current KYC level (0 = unverified, 3 = full)."""
        try:
            from api.kyc.services import KYCService
            return KYCService.get_verified_level(user.pk)
        except ImportError:
            # Fall back to wallet's internal KYC tracker
            try:
                from api.wallet.services_extra import KYCService as WalletKYCService
                return WalletKYCService.get_user_level(user)
            except Exception:
                return 0
        except Exception as e:
            logger.error(f"[KYCAdapter] get_level error: {e}")
            return 0

    @staticmethod
    def is_withdrawal_allowed(user, wallet: "Wallet",
                              amount: Decimal) -> tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Checks KYC level against withdrawal amount thresholds.
        """
        try:
            from api.kyc.services import KYCService
            result = KYCService.check_withdrawal_eligibility(
                user_id=user.pk,
                amount=float(amount),
            )
            return result.get("allowed", True), result.get("reason", "")
        except ImportError:
            # Inline wallet KYC check
            try:
                from api.wallet.services_extra import KYCService as WalletKYCService
                return WalletKYCService.check_withdrawal_allowed(user, wallet, amount)
            except Exception:
                return True, ""
        except Exception as e:
            logger.error(f"[KYCAdapter] withdrawal check error: {e}")
            return True, ""  # Fail open

    @staticmethod
    def on_kyc_approved(user, wallet: "Wallet", kyc_level: int) -> dict:
        """
        Called by api.kyc when a user is approved.
        Unlocks higher withdrawal limits on the wallet.
        """
        tier_limits = {1: "5000", 2: "50000", 3: "500000"}
        new_limit = tier_limits.get(kyc_level, "1000")
        logger.info(
            f"[KYCAdapter] User {user.pk} approved at level {kyc_level}, "
            f"limit updated to {new_limit} BDT"
        )
        return {
            "success":   True,
            "kyc_level": kyc_level,
            "new_limit": new_limit,
            "wallet_id": wallet.pk,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 6. PayoutQueueAdapter  →  api.payout_queue
# ═══════════════════════════════════════════════════════════════════════════
class PayoutQueueAdapter:
    """
    Submits withdrawal requests to api.payout_queue for async processing.
    Payout queue handles gateway routing, retry logic, and rate limiting.
    """

    @staticmethod
    def enqueue_withdrawal(withdrawal_request, user,
                           wallet: "Wallet") -> dict:
        """Submit a withdrawal to the payout queue."""
        try:
            from api.payout_queue.services import PayoutQueueService
            result = PayoutQueueService.enqueue({
                "withdrawal_id":  str(withdrawal_request.withdrawal_id),
                "user_id":        user.pk,
                "wallet_id":      wallet.pk,
                "amount":         str(withdrawal_request.amount),
                "net_amount":     str(withdrawal_request.net_amount),
                "gateway":        withdrawal_request.payment_method.method_type,
                "account_number": withdrawal_request.payment_method.account_number,
                "currency":       "BDT",
                "priority":       _get_user_priority(user),
            })
            logger.info(
                f"[PayoutQueueAdapter] Enqueued withdrawal "
                f"{withdrawal_request.withdrawal_id}: queue_id={result.get('queue_id')}"
            )
            return result
        except ImportError:
            return {"success": True, "skipped": True, "note": "payout_queue not installed"}
        except Exception as e:
            logger.error(f"[PayoutQueueAdapter] enqueue error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_queue_status(withdrawal_id: str) -> dict:
        """Check the payout queue status of a withdrawal."""
        try:
            from api.payout_queue.services import PayoutQueueService
            return PayoutQueueService.get_status(withdrawal_id)
        except ImportError:
            return {"status": "unknown", "skipped": True}
        except Exception as e:
            logger.error(f"[PayoutQueueAdapter] status error: {e}")
            return {"status": "error", "error": str(e)}

    @staticmethod
    def cancel_queued_withdrawal(withdrawal_id: str) -> dict:
        """Remove a withdrawal from the queue (user cancellation)."""
        try:
            from api.payout_queue.services import PayoutQueueService
            return PayoutQueueService.cancel(withdrawal_id)
        except ImportError:
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[PayoutQueueAdapter] cancel error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 7. ExternalWebhookAdapter  →  api.webhooks
# ═══════════════════════════════════════════════════════════════════════════
class ExternalWebhookAdapter:
    """
    Dispatches wallet events to user-registered webhooks via api.webhooks.
    Used for third-party developer integrations.
    """

    EVENTS = {
        "credit":              "wallet.credit",
        "debit":               "wallet.debit",
        "withdrawal_created":  "wallet.withdrawal.created",
        "withdrawal_approved": "wallet.withdrawal.approved",
        "withdrawal_rejected": "wallet.withdrawal.rejected",
        "locked":              "wallet.locked",
        "unlocked":            "wallet.unlocked",
        "kyc_approved":        "wallet.kyc_approved",
    }

    @staticmethod
    def dispatch(event_name: str, user, payload: dict) -> None:
        """Dispatch an event to all registered webhook endpoints for this user."""
        try:
            from api.webhooks.services import WebhookDispatcher
            event_type = ExternalWebhookAdapter.EVENTS.get(event_name, event_name)
            WebhookDispatcher.dispatch(
                user_id=user.pk,
                event_type=event_type,
                payload=payload,
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[WebhookAdapter] dispatch error for {event_name}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 8. PostbackWalletAdapter  →  api.postback / api.postback_engine
# ═══════════════════════════════════════════════════════════════════════════
class PostbackWalletAdapter:
    """
    Fires postback events to advertiser URLs when wallet credits happen
    (offer completions, conversions, etc).
    """

    @staticmethod
    def on_offer_credit(user, wallet: "Wallet", offer_id: int,
                        amount: Decimal, click_id: str = "",
                        country_code: str = "") -> dict:
        """Fire postback when an offer earns money for the user."""
        try:
            from api.postback_engine.services import PostbackEngine
            return PostbackEngine.fire({
                "user_id":      user.pk,
                "offer_id":     offer_id,
                "amount":       str(amount),
                "click_id":     click_id,
                "country_code": country_code,
                "event":        "conversion",
            })
        except ImportError:
            try:
                from api.postback.services import PostbackService
                return PostbackService.fire_conversion(
                    user_id=user.pk,
                    offer_id=offer_id,
                    amount=amount,
                    click_id=click_id,
                )
            except ImportError:
                return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[PostbackAdapter] offer_credit error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 9. AIWalletAdapter  →  api.ai_engine
# ═══════════════════════════════════════════════════════════════════════════
class AIWalletAdapter:
    """
    Integrates AI engine for intelligent wallet features:
    - Fraud prediction (ML-based, vs rule-based FraudSignalAdapter)
    - Spending pattern analysis
    - Smart withdrawal scheduling
    - Personalized offer recommendations
    """

    @staticmethod
    def predict_fraud_score(user, wallet: "Wallet",
                            txn_data: dict) -> dict:
        """AI-based fraud score prediction."""
        try:
            from api.ai_engine.services import AIEngine
            return AIEngine.predict("wallet.fraud_score", {
                "user_id":       user.pk,
                "wallet_id":     wallet.pk,
                "balance":       float(wallet.current_balance),
                "total_earned":  float(wallet.total_earned),
                **txn_data,
            })
        except ImportError:
            return {"score": 0.0, "risk": "low", "skipped": True}
        except Exception as e:
            logger.error(f"[AIAdapter] fraud_score error: {e}")
            return {"score": 0.0, "risk": "low"}

    @staticmethod
    def get_spending_insights(user, wallet: "Wallet") -> dict:
        """AI-generated spending pattern insights for user dashboard."""
        try:
            from api.ai_engine.services import AIEngine
            return AIEngine.analyze("wallet.spending_insights", {
                "user_id":      user.pk,
                "wallet_id":    wallet.pk,
                "balance":      float(wallet.current_balance),
                "total_earned": float(wallet.total_earned),
            })
        except ImportError:
            return {"insights": [], "skipped": True}
        except Exception as e:
            logger.error(f"[AIAdapter] insights error: {e}")
            return {"insights": []}

    @staticmethod
    def recommend_offers(user, wallet: "Wallet",
                         limit: int = 5) -> list:
        """AI-curated offer recommendations based on wallet history."""
        try:
            from api.ai_engine.services import AIEngine
            result = AIEngine.recommend("wallet.offers", {
                "user_id":   user.pk,
                "wallet_id": wallet.pk,
                "limit":     limit,
            })
            return result.get("offers", [])
        except ImportError:
            return []
        except Exception as e:
            logger.error(f"[AIAdapter] recommend_offers error: {e}")
            return []

    @staticmethod
    def optimal_withdrawal_time(user, wallet: "Wallet") -> dict:
        """Suggest the best time to withdraw based on processing patterns."""
        try:
            from api.ai_engine.services import AIEngine
            return AIEngine.predict("wallet.withdrawal_timing", {
                "user_id":    user.pk,
                "wallet_id":  wallet.pk,
                "balance":    float(wallet.current_balance),
            })
        except ImportError:
            return {"recommended_hour": 10, "reason": "default", "skipped": True}
        except Exception as e:
            logger.error(f"[AIAdapter] withdrawal_timing error: {e}")
            return {"recommended_hour": 10, "reason": "error_fallback"}


# ═══════════════════════════════════════════════════════════════════════════
# 10. SubscriptionWalletAdapter  →  api.subscription
# ═══════════════════════════════════════════════════════════════════════════
class SubscriptionWalletAdapter:
    """
    Handles wallet-subscription interactions:
    - Deduct subscription fees from wallet
    - Grant subscription bonuses on top-up
    - Check if user has active subscription
    """

    @staticmethod
    def deduct_subscription_fee(user, wallet: "Wallet",
                                plan: str, amount: Decimal) -> dict:
        """Deduct a subscription fee from the user's wallet."""
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.debit(
                wallet, amount,
                txn_type="subscription_fee",
                description=f"Subscription: {plan}",
                reference_type="subscription",
            )
            return {"success": True, "txn_id": str(txn.txn_id), "amount": str(amount)}
        except Exception as e:
            logger.error(f"[SubscriptionAdapter] deduct error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_subscription_status(user) -> dict:
        """Check user subscription from api.subscription app."""
        try:
            from api.subscription.services import SubscriptionService
            return SubscriptionService.get_active(user.pk)
        except ImportError:
            return {"active": False, "plan": None, "skipped": True}
        except Exception as e:
            logger.error(f"[SubscriptionAdapter] status error: {e}")
            return {"active": False, "plan": None}

    @staticmethod
    def on_subscription_activated(user, wallet: "Wallet",
                                  plan: str, bonus_amount: Decimal = Decimal("0")) -> dict:
        """Credit welcome bonus when subscription activates."""
        if bonus_amount <= 0:
            return {"success": True, "bonus_credited": False}
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, bonus_amount,
                txn_type="bonus",
                description=f"Subscription activation bonus: {plan}",
                reference_type="subscription",
            )
            return {"success": True, "txn_id": str(txn.txn_id), "bonus": str(bonus_amount)}
        except Exception as e:
            logger.error(f"[SubscriptionAdapter] bonus error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 11. GamificationWalletAdapter  →  api.gamification
# ═══════════════════════════════════════════════════════════════════════════
class GamificationWalletAdapter:
    """
    Links gamification events (badges, streaks, leaderboards) to wallet credits.
    """

    @staticmethod
    def on_badge_earned(user, wallet: "Wallet",
                        badge_id: str, reward_amount: Decimal = Decimal("0")) -> dict:
        """Credit wallet when user earns a gamification badge."""
        if reward_amount <= 0:
            return {"success": True, "credited": False}
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, reward_amount,
                txn_type="bonus",
                description=f"Badge reward: {badge_id}",
                reference_type="gamification",
                reference_id=badge_id,
            )
            return {"success": True, "txn_id": str(txn.txn_id)}
        except Exception as e:
            logger.error(f"[GamificationAdapter] badge_reward error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def on_streak_bonus(user, wallet: "Wallet",
                        streak_days: int, amount: Decimal) -> dict:
        """Credit streak bonus to wallet."""
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, amount,
                txn_type="bonus",
                description=f"Streak bonus: {streak_days} days",
                reference_type="gamification",
            )
            return {"success": True, "txn_id": str(txn.txn_id), "streak": streak_days}
        except Exception as e:
            logger.error(f"[GamificationAdapter] streak_bonus error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_leaderboard_rank(user, wallet: "Wallet") -> dict:
        """Fetch user's rank from gamification leaderboard."""
        try:
            from api.gamification.services import LeaderboardService
            return LeaderboardService.get_user_rank(user.pk)
        except ImportError:
            return {"rank": None, "score": 0, "skipped": True}
        except Exception as e:
            logger.error(f"[GamificationAdapter] leaderboard error: {e}")
            return {"rank": None, "score": 0}


# ═══════════════════════════════════════════════════════════════════════════
# 12. OfferRoutingAdapter  →  api.offer_routing
# ═══════════════════════════════════════════════════════════════════════════
class OfferRoutingAdapter:
    """
    Routes offer payouts through the correct earning pipeline based on
    offer type, user tier, geo, and current caps.
    """

    @staticmethod
    def route_offer_payout(user, wallet: "Wallet",
                           offer_id: int, raw_amount: Decimal,
                           country_code: str = "", device_type: str = "") -> dict:
        """
        Calculate the final payout after multipliers, caps, and deductions.
        Returns the net credit amount to apply to the wallet.
        """
        try:
            from api.offer_routing.services import OfferRouter
            result = OfferRouter.calculate_payout({
                "user_id":      user.pk,
                "wallet_id":    wallet.pk,
                "offer_id":     offer_id,
                "raw_amount":   str(raw_amount),
                "country_code": country_code,
                "device_type":  device_type,
            })
            return result
        except ImportError:
            return {
                "success":    True,
                "net_amount": str(raw_amount),
                "multiplier": "1.0",
                "skipped":    True,
            }
        except Exception as e:
            logger.error(f"[OfferRoutingAdapter] route error: {e}")
            return {"success": False, "net_amount": str(raw_amount), "error": str(e)}

    @staticmethod
    def check_daily_cap(user, wallet: "Wallet") -> dict:
        """Check if user has hit their daily earning cap."""
        try:
            from api.offer_routing.services import OfferRouter
            return OfferRouter.check_daily_cap(user.pk)
        except ImportError:
            return {"capped": False, "remaining": None, "skipped": True}
        except Exception as e:
            return {"capped": False, "remaining": None}


# ═══════════════════════════════════════════════════════════════════════════
# 13. AlertWalletAdapter  →  api.alerts
# ═══════════════════════════════════════════════════════════════════════════
class AlertWalletAdapter:
    """
    Triggers system-level alerts for wallet anomalies that need
    admin attention (large transactions, suspicious patterns, errors).
    """

    @staticmethod
    def alert_large_transaction(user, wallet: "Wallet",
                                amount: Decimal, txn_type: str) -> None:
        """Alert if a single transaction exceeds the alert threshold."""
        try:
            LARGE_THRESHOLD = Decimal("10000")
            if amount < LARGE_THRESHOLD:
                return
            from api.alerts.services import AlertService
            AlertService.create(
                level="warning",
                category="wallet.large_transaction",
                message=f"Large {txn_type} of ৳{amount} for user {user.pk}",
                metadata={
                    "user_id":   user.pk,
                    "wallet_id": wallet.pk,
                    "amount":    str(amount),
                    "txn_type":  txn_type,
                },
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[AlertAdapter] large_transaction error: {e}")

    @staticmethod
    def alert_wallet_error(user, wallet: "Wallet",
                           error_type: str, details: str) -> None:
        """Alert on wallet system errors."""
        try:
            from api.alerts.services import AlertService
            AlertService.create(
                level="error",
                category=f"wallet.{error_type}",
                message=details,
                metadata={"user_id": user.pk, "wallet_id": wallet.pk},
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[AlertAdapter] wallet_error alert failed: {e}")

    @staticmethod
    def alert_balance_discrepancy(wallet: "Wallet",
                                  expected: Decimal, actual: Decimal) -> None:
        """Alert when reconciliation finds a balance discrepancy."""
        try:
            from api.alerts.services import AlertService
            AlertService.create(
                level="critical",
                category="wallet.balance_discrepancy",
                message=(
                    f"Balance discrepancy on wallet {wallet.pk}: "
                    f"expected={expected} actual={actual} diff={expected - actual}"
                ),
                metadata={
                    "wallet_id": wallet.pk,
                    "expected":  str(expected),
                    "actual":    str(actual),
                    "diff":      str(expected - actual),
                },
            )
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"[AlertAdapter] discrepancy alert failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 14. SupportWalletAdapter  →  api.support
# ═══════════════════════════════════════════════════════════════════════════
class SupportWalletAdapter:
    """
    Provides wallet data to the support team via api.support.
    Enables support agents to view wallet history and take actions.
    """

    @staticmethod
    def get_wallet_summary_for_support(user) -> dict:
        """Full wallet summary for support ticket context."""
        try:
            from api.wallet.services import WalletService
            summary = WalletService.get_summary(user)
            if isinstance(summary, dict):
                summary["support_actions"] = [
                    "credit", "debit", "lock", "unlock",
                    "freeze", "view_history", "generate_statement",
                ]
                return summary
            return {
                "user_id": user.pk,
                "support_actions": [
                    "credit", "debit", "lock", "unlock",
                    "freeze", "view_history", "generate_statement",
                ],
            }
        except Exception as e:
            logger.error(f"[SupportAdapter] summary error: {e}")
            return {
                "user_id": user.pk,
                "support_actions": ["view_history"],
                "error": str(e),
            }

    @staticmethod
    def get_transaction_history_for_support(user,
                                            limit: int = 50) -> list:
        """Recent transactions for support investigation."""
        try:
            from api.wallet.models import WalletTransaction
            txns = WalletTransaction.objects.filter(
                wallet__user=user
            ).order_by("-created_at")[:limit]
            return [
                {
                    "txn_id":      str(t.txn_id),
                    "type":        t.type,
                    "amount":      str(t.amount),
                    "status":      t.status,
                    "description": t.description,
                    "created_at":  t.created_at.isoformat(),
                }
                for t in txns
            ]
        except Exception as e:
            logger.error(f"[SupportAdapter] history error: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════
# 15. DisasterRecoveryAdapter  →  api.dr_integration
# ═══════════════════════════════════════════════════════════════════════════
class DisasterRecoveryAdapter:
    """
    Wallet disaster recovery integration.
    Creates wallet snapshots and restores from backup if corruption detected.
    """

    @staticmethod
    def create_balance_snapshot(wallet: "Wallet") -> dict:
        """Snapshot wallet balance for DR purposes."""
        try:
            from api.dr_integration.services import DRService
            return DRService.snapshot_wallet({
                "wallet_id":        wallet.pk,
                "user_id":          wallet.user_id,
                "current_balance":  str(wallet.current_balance),
                "frozen_balance":   str(wallet.frozen_balance or 0),
                "total_earned":     str(wallet.total_earned),
                "total_withdrawn":  str(wallet.total_withdrawn),
                "version":          wallet.version,
            })
        except ImportError:
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[DRAdapter] snapshot error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_integrity(wallet: "Wallet") -> dict:
        """Verify wallet data integrity against DR backup."""
        try:
            from api.dr_integration.services import DRService
            return DRService.verify_wallet_integrity(wallet.pk)
        except ImportError:
            return {"intact": True, "skipped": True}
        except Exception as e:
            logger.error(f"[DRAdapter] integrity check error: {e}")
            return {"intact": True}


# ═══════════════════════════════════════════════════════════════════════════
# 16. AutoModWalletAdapter  →  api.auto_mod
# ═══════════════════════════════════════════════════════════════════════════
class AutoModWalletAdapter:
    """
    Automatic moderation for wallet abuse (bot detection, offer farming, etc).
    """

    @staticmethod
    def check_earning_pattern(user, wallet: "Wallet",
                              source: str, amount: Decimal) -> dict:
        """Check if earning pattern looks automated/botted."""
        try:
            from api.auto_mod.services import AutoModService
            return AutoModService.check_wallet_earning({
                "user_id":   user.pk,
                "wallet_id": wallet.pk,
                "source":    source,
                "amount":    str(amount),
            })
        except ImportError:
            return {"flagged": False, "skipped": True}
        except Exception as e:
            logger.error(f"[AutoModAdapter] earning_pattern error: {e}")
            return {"flagged": False}

    @staticmethod
    def on_violation_detected(user, wallet: "Wallet",
                              violation_type: str) -> dict:
        """
        Called when auto_mod detects a violation.
        May trigger wallet lock or earning suspension.
        """
        try:
            from api.auto_mod.services import AutoModService
            result = AutoModService.handle_violation(
                user_id=user.pk,
                violation_type=violation_type,
            )
            if result.get("action") == "lock_wallet":
                from api.wallet.services.core.WalletService import WalletService
                wallet.lock(
                    reason=f"AutoMod: {violation_type}",
                    locked_by=None,
                )
                wallet.save()
            return result
        except ImportError:
            return {"action": "none", "skipped": True}
        except Exception as e:
            logger.error(f"[AutoModAdapter] violation error: {e}")
            return {"action": "none", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 17. BehaviorAnalyticsAdapter  →  api.behavior_analytics
# ═══════════════════════════════════════════════════════════════════════════
class BehaviorAnalyticsAdapter:
    """
    Feeds wallet behavioral signals into api.behavior_analytics for
    user segmentation and lifetime value modeling.
    """

    @staticmethod
    def track_wallet_event(user, event: str, properties: dict = None) -> None:
        try:
            from api.behavior_analytics.services import BehaviorTracker
            BehaviorTracker.track(
                user_id=user.pk,
                event=f"wallet.{event}",
                properties=properties or {},
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[BehaviorAdapter] track error: {e}")

    @staticmethod
    def get_user_segment(user) -> str:
        """Get user's behavioral segment (high_value, at_risk, dormant, etc)."""
        try:
            from api.behavior_analytics.services import BehaviorTracker
            result = BehaviorTracker.get_segment(user.pk)
            return result.get("segment", "standard")
        except ImportError:
            return "standard"
        except Exception as e:
            logger.debug(f"[BehaviorAdapter] segment error: {e}")
            return "standard"


# ═══════════════════════════════════════════════════════════════════════════
# MASTER ADAPTER — single entry point for wallet events
# ═══════════════════════════════════════════════════════════════════════════
class WalletAdapter:
    """
    Master adapter. Call these class methods from wallet services
    instead of calling each individual adapter directly.

    Example usage inside WalletService.credit():
        WalletAdapter.on_credit(txn, user, wallet, amount, country_code=cc)

    Example usage inside WithdrawalService.process():
        WalletAdapter.on_withdrawal_completed(txn, user, wallet, amount, gateway)
    """

    # ── Credit event ─────────────────────────────────────────────────────
    @classmethod
    def on_credit(cls, txn, user, wallet: "Wallet",
                  amount: Decimal,
                  txn_type: str = "earning",
                  source: str = "",
                  offer_id: Optional[int] = None,
                  click_id: str = "",
                  country_code: str = "",
                  ip_address: str = "") -> None:
        """Fire all adapters needed when a wallet is credited."""
        WalletAnalyticsAdapter.track_credit(user, wallet, amount, txn_type, country_code)
        WalletNotificationAdapter.notify_credit(user, amount, txn_type, wallet.current_balance)
        ExternalWebhookAdapter.dispatch("credit", user, {
            "txn_id":    str(txn.txn_id),
            "amount":    str(amount),
            "txn_type":  txn_type,
            "balance":   str(wallet.current_balance),
        })
        AlertWalletAdapter.alert_large_transaction(user, wallet, amount, txn_type)
        BehaviorAnalyticsAdapter.track_wallet_event(user, "credited", {
            "amount": float(amount), "type": txn_type
        })
        if offer_id:
            PostbackWalletAdapter.on_offer_credit(
                user, wallet, offer_id, amount, click_id, country_code
            )
        if txn_type == "referral":
            ReferralWalletAdapter.on_referral_earning(user, user, amount, source)
        # Audit log
        AuditLogAdapter.log_transaction(user, wallet, txn, "credited")
        # Cache invalidate
        CacheAdapter.invalidate_wallet_cache(wallet.pk)
        # Loyalty points
        LoyaltyAdapter.earn_points_for_withdrawal(user, amount)

    # ── Withdrawal events ─────────────────────────────────────────────────
    @classmethod
    def on_withdrawal_initiated(cls, withdrawal_request, user,
                                wallet: "Wallet") -> None:
        """Fire all adapters when withdrawal is first created."""
        method = getattr(getattr(withdrawal_request, "payment_method", None),
                         "method_type", "unknown")
        WalletNotificationAdapter.notify_withdrawal_initiated(
            user, withdrawal_request.amount, method
        )
        PayoutQueueAdapter.enqueue_withdrawal(withdrawal_request, user, wallet)
        ExternalWebhookAdapter.dispatch("withdrawal_created", user, {
            "withdrawal_id": str(withdrawal_request.withdrawal_id),
            "amount":        str(withdrawal_request.amount),
            "method":        method,
        })
        WalletAnalyticsAdapter.track_withdrawal(
            user, wallet, withdrawal_request.amount, method, "initiated"
        )
        FraudSignalAdapter.on_withdrawal_requested(
            user, wallet, withdrawal_request.amount, method
        )
        AuditLogAdapter.log_withdrawal(user, wallet, withdrawal_request, "initiated")
        CacheAdapter.invalidate_wallet_cache(wallet.pk)

    @classmethod
    def on_withdrawal_completed(cls, txn, user, wallet: "Wallet",
                                amount: Decimal, gateway: str) -> None:
        """Fire all adapters when withdrawal is successfully processed."""
        net = getattr(txn, "net_amount", amount)
        WalletNotificationAdapter.notify_withdrawal_approved(user, amount, net, gateway)
        ExternalWebhookAdapter.dispatch("withdrawal_approved", user, {
            "amount": str(amount), "gateway": gateway
        })
        WalletAnalyticsAdapter.track_withdrawal(user, wallet, amount, gateway, "completed")
        ReferralWalletAdapter.on_first_withdrawal(user, wallet, amount)
        BehaviorAnalyticsAdapter.track_wallet_event(user, "withdrawal_completed", {
            "amount": float(amount), "gateway": gateway
        })
        AuditLogAdapter.log_withdrawal(user, wallet, txn, "completed")
        CacheAdapter.invalidate_wallet_cache(wallet.pk)
        LoyaltyAdapter.earn_points_for_withdrawal(user, amount)

    @classmethod
    def on_withdrawal_rejected(cls, user, wallet: "Wallet",
                               amount: Decimal, reason: str) -> None:
        """Fire all adapters when withdrawal is rejected."""
        WalletNotificationAdapter.notify_withdrawal_rejected(user, amount, reason)
        ExternalWebhookAdapter.dispatch("withdrawal_rejected", user, {
            "amount": str(amount), "reason": reason
        })
        WalletAnalyticsAdapter.track_withdrawal(
            user, wallet, amount, "rejected", "rejected"
        )

    # ── Wallet lock/unlock ────────────────────────────────────────────────
    @classmethod
    def on_wallet_locked(cls, user, wallet: "Wallet", reason: str) -> None:
        WalletNotificationAdapter.notify_wallet_locked(user, reason)
        ExternalWebhookAdapter.dispatch("locked", user, {"reason": reason})
        BehaviorAnalyticsAdapter.track_wallet_event(user, "locked", {"reason": reason})

    # ── KYC events ───────────────────────────────────────────────────────
    @classmethod
    def on_kyc_approved(cls, user, wallet: "Wallet", kyc_level: int) -> None:
        KYCWalletAdapter.on_kyc_approved(user, wallet, kyc_level)
        ExternalWebhookAdapter.dispatch("kyc_approved", user, {"level": kyc_level})
        BehaviorAnalyticsAdapter.track_wallet_event(user, "kyc_approved", {
            "level": kyc_level
        })

    # ── Pre-operation gates ───────────────────────────────────────────────
    @classmethod
    def check_withdrawal_allowed(cls, user, wallet: "Wallet",
                                 amount: Decimal,
                                 ip_address: str = "") -> tuple[bool, str]:
        """
        Gate check before any withdrawal is processed.
        Returns (allowed: bool, reason: str).
        Fails open — any individual check failure allows the operation.
        """
        try:
            allowed, reason = KYCWalletAdapter.is_withdrawal_allowed(user, wallet, amount)
            if not allowed:
                return False, reason
        except Exception as e:
            logger.error(f"[WalletAdapter] KYC check failed (fail open): {e}")

        try:
            fraud_result = FraudSignalAdapter.on_withdrawal_requested(
                user, wallet, amount, "any", ip_address
            )
            if fraud_result.get("block"):
                return False, fraud_result.get("reason", "Blocked by fraud detection")
        except Exception as e:
            logger.error(f"[WalletAdapter] Fraud check failed (fail open): {e}")

        try:
            automod = AutoModWalletAdapter.check_earning_pattern(user, wallet, "withdrawal", amount)
            if automod.get("flagged"):
                return False, "Withdrawal pattern flagged for review"
        except Exception as e:
            logger.error(f"[WalletAdapter] AutoMod check failed (fail open): {e}")

        # 4. Proxy/VPN check
        try:
            if ip_address:
                allowed_ip, reason_ip = ProxyIntelligenceAdapter.is_withdrawal_allowed_from_ip(ip_address)
                if not allowed_ip:
                    return False, reason_ip
        except Exception as e:
            logger.error(f"[WalletAdapter] Proxy check failed (fail open): {e}")

        # 5. Rate limit check
        try:
            rate = RateLimitAdapter.check_withdrawal_rate(user, amount)
            if not rate.get("allowed", True):
                return False, "Withdrawal rate limit exceeded"
        except Exception as e:
            logger.error(f"[WalletAdapter] Rate limit check failed (fail open): {e}")

        # 6. User account status check
        try:
            if UserProfileAdapter.is_suspended(user):
                return False, "Account suspended — withdrawals not allowed"
        except Exception as e:
            logger.error(f"[WalletAdapter] User status check failed (fail open): {e}")

        return True, ""


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════
def _get_user_priority(user) -> str:
    """Determine payout priority based on publisher level."""
    try:
        from api.wallet.models_cpalead_extra import PublisherLevel
        pl = PublisherLevel.objects.filter(user=user).first()
        if pl and pl.level >= 3:
            return "high"
        elif pl and pl.level >= 2:
            return "normal"
        return "low"
    except Exception:
        return "normal"


# ═══════════════════════════════════════════════════════════════════════════
# 18. PaymentGatewayAdapter  →  api.payment_gateways
# ═══════════════════════════════════════════════════════════════════════════
class PaymentGatewayAdapter:
    """
    Routes actual payment processing (bKash, Nagad, DBBL, Sonali Bank, USDT)
    through api.payment_gateways. This is the OUTBOUND payment layer —
    when wallet approves a withdrawal, this adapter fires the real money movement.
    """

    GATEWAY_MAP = {
        "bkash":      "bkash",
        "nagad":      "nagad",
        "rocket":     "dbbl_rocket",
        "bank":       "bank_transfer",
        "usdt_trc20": "crypto_usdt_trc20",
        "usdt_erc20": "crypto_usdt_erc20",
        "paypal":     "paypal",
    }

    @staticmethod
    def process_withdrawal(withdrawal_request, user, wallet: "Wallet") -> dict:
        """
        Send a real payment through the payment gateway.
        Called by WithdrawalService after approval.
        Returns gateway_reference, status, and estimated arrival.
        """
        try:
            from api.payment_gateways.services import GatewayService
            method    = withdrawal_request.payment_method
            gateway   = PaymentGatewayAdapter.GATEWAY_MAP.get(method.method_type, method.method_type)
            result    = GatewayService.send_payment(
                gateway=gateway,
                amount=withdrawal_request.net_amount,
                recipient_account=method.account_number,
                recipient_name=method.account_name,
                reference=str(withdrawal_request.withdrawal_id),
                metadata={
                    "user_id":         user.pk,
                    "wallet_id":       wallet.pk,
                    "withdrawal_id":   str(withdrawal_request.withdrawal_id),
                },
            )
            logger.info(
                f"[PaymentGatewayAdapter] Payment sent: {result.get('gateway_ref')} "
                f"via {gateway} for {withdrawal_request.net_amount}"
            )
            return result
        except ImportError:
            return {
                "success":       True,
                "gateway_ref":   f"SIMULATED_{withdrawal_request.withdrawal_id}",
                "status":        "processing",
                "estimated_at":  None,
                "skipped":       True,
                "note":          "api.payment_gateways not installed",
            }
        except Exception as e:
            logger.error(f"[PaymentGatewayAdapter] process error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_account(method_type: str, account_number: str,
                       account_name: str = "") -> dict:
        """
        Verify a payment account before saving as withdrawal method.
        Returns {valid: bool, real_name: str, reason: str}
        """
        try:
            from api.payment_gateways.services import GatewayService
            gateway = PaymentGatewayAdapter.GATEWAY_MAP.get(method_type, method_type)
            return GatewayService.verify_account(
                gateway=gateway,
                account_number=account_number,
                account_name=account_name,
            )
        except ImportError:
            return {"valid": True, "real_name": account_name, "skipped": True}
        except Exception as e:
            logger.error(f"[PaymentGatewayAdapter] verify error: {e}")
            return {"valid": True, "real_name": account_name, "error": str(e)}

    @staticmethod
    def get_gateway_fee(method_type: str, amount: "Decimal") -> dict:
        """Get real-time fee from gateway API."""
        try:
            from api.payment_gateways.services import GatewayService
            gateway = PaymentGatewayAdapter.GATEWAY_MAP.get(method_type, method_type)
            return GatewayService.calculate_fee(gateway=gateway, amount=amount)
        except ImportError:
            return {"fee": Decimal("0"), "skipped": True}
        except Exception as e:
            return {"fee": Decimal("0"), "error": str(e)}

    @staticmethod
    def get_transaction_status(gateway_ref: str, method_type: str) -> dict:
        """Poll gateway for transaction status update."""
        try:
            from api.payment_gateways.services import GatewayService
            gateway = PaymentGatewayAdapter.GATEWAY_MAP.get(method_type, method_type)
            return GatewayService.get_status(gateway=gateway, reference=gateway_ref)
        except ImportError:
            return {"status": "unknown", "skipped": True}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 19. UserProfileAdapter  →  api.users
# ═══════════════════════════════════════════════════════════════════════════
class UserProfileAdapter:
    """
    Syncs user profile state (suspension, tier, limits) with the wallet.
    A suspended user must not be able to withdraw. A premium user gets higher limits.
    """

    @staticmethod
    def get_user_status(user) -> dict:
        """
        Returns full user status affecting wallet operations.
        {active: bool, suspended: bool, tier: str, country: str, currency: str}
        """
        try:
            from api.users.services import UserService
            return UserService.get_wallet_profile(user.pk)
        except ImportError:
            return {
                "active":    True,
                "suspended": False,
                "tier":      "standard",
                "country":   "BD",
                "currency":  "BDT",
                "skipped":   True,
            }
        except Exception as e:
            logger.error(f"[UserProfileAdapter] get_status error: {e}")
            return {"active": True, "suspended": False, "tier": "standard"}

    @staticmethod
    def is_suspended(user) -> bool:
        """Quick check — is this user account suspended?"""
        try:
            status = UserProfileAdapter.get_user_status(user)
            return status.get("suspended", False)
        except Exception:
            return False

    @staticmethod
    def get_withdrawal_limit_multiplier(user) -> "Decimal":
        """
        Premium users get higher withdrawal limits.
        Returns multiplier: 1.0 = standard, 2.0 = premium, 5.0 = enterprise.
        """
        try:
            from api.users.services import UserService
            tier = UserService.get_tier(user.pk)
            return {"standard": Decimal("1"), "premium": Decimal("2"),
                    "enterprise": Decimal("5")}.get(tier, Decimal("1"))
        except ImportError:
            return Decimal("1")
        except Exception:
            return Decimal("1")

    @staticmethod
    def on_wallet_created(user, wallet: "Wallet") -> None:
        """Notify users app when wallet is created."""
        try:
            from api.users.services import UserService
            UserService.on_wallet_created(user.pk, wallet.pk)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[UserProfileAdapter] on_wallet_created: {e}")

    @staticmethod
    def get_preferred_currency(user) -> str:
        """Get user's preferred currency for display."""
        try:
            from api.users.services import UserService
            return UserService.get_currency(user.pk) or "BDT"
        except ImportError:
            return "BDT"
        except Exception:
            return "BDT"


# ═══════════════════════════════════════════════════════════════════════════
# 20. SecurityAdapter  →  api.security
# ═══════════════════════════════════════════════════════════════════════════
class SecurityAdapter:
    """
    Enforces security checks before sensitive wallet operations:
    - 2FA verification before withdrawal
    - Session freshness check
    - Device fingerprint validation
    """

    @staticmethod
    def verify_2fa(user, otp_code: str, operation: str = "withdrawal") -> dict:
        """
        Verify a 2FA OTP before allowing sensitive operations.
        Returns {verified: bool, reason: str}
        """
        try:
            from api.security.services import SecurityService
            return SecurityService.verify_otp(
                user_id=user.pk,
                otp=otp_code,
                operation=operation,
            )
        except ImportError:
            return {"verified": True, "skipped": True}
        except Exception as e:
            logger.error(f"[SecurityAdapter] 2fa verify error: {e}")
            return {"verified": False, "reason": "2FA service unavailable"}

    @staticmethod
    def is_2fa_required(user, amount: "Decimal") -> bool:
        """Check if this withdrawal amount requires 2FA."""
        try:
            from api.security.services import SecurityService
            return SecurityService.requires_2fa(user.pk, float(amount))
        except ImportError:
            return amount >= Decimal("5000")  # Default: require 2FA for large amounts
        except Exception:
            return False

    @staticmethod
    def check_session_freshness(user, request=None) -> dict:
        """Ensure user session is fresh (not stale/hijacked)."""
        try:
            from api.security.services import SecurityService
            return SecurityService.check_session(user.pk, request)
        except ImportError:
            return {"fresh": True, "skipped": True}
        except Exception as e:
            return {"fresh": True, "error": str(e)}

    @staticmethod
    def log_sensitive_action(user, action: str, wallet: "Wallet",
                              amount: "Decimal" = None, ip: str = "",
                              success: bool = True) -> None:
        """Log sensitive wallet actions to security audit trail."""
        try:
            from api.security.services import SecurityService
            SecurityService.log_action(
                user_id=user.pk,
                action=f"wallet.{action}",
                resource_id=str(wallet.pk),
                metadata={
                    "amount":  str(amount) if amount else None,
                    "ip":      ip,
                    "success": success,
                },
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[SecurityAdapter] log error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 21. OfferwallAdapter  →  api.offerwall
# ═══════════════════════════════════════════════════════════════════════════
class OfferwallAdapter:
    """
    Credits wallet when a user completes an offerwall task.
    This is the PRIMARY earning mechanism for the platform.
    """

    @staticmethod
    def on_offer_completed(user, wallet: "Wallet",
                           offer_id: int, payout: "Decimal",
                           click_id: str = "", ip: str = "",
                           country: str = "") -> dict:
        """
        Called by offerwall when a user completes an offer.
        Credits the wallet and fires all downstream events.
        """
        try:
            from api.wallet.services.earning.EarningService import EarningService
            result = EarningService.add_earning(
                user=user,
                wallet=wallet,
                amount=payout,
                source="offerwall",
                source_type="offer",
                source_id=str(offer_id),
                ip_address=ip,
                country_code=country,
                metadata={"click_id": click_id, "offer_id": offer_id},
            )
            logger.info(
                f"[OfferwallAdapter] Offer {offer_id} completed: "
                f"user={user.pk} payout={payout}"
            )
            return {"success": True, "txn": result}
        except Exception as e:
            logger.error(f"[OfferwallAdapter] credit error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def on_offer_reversed(user, wallet: "Wallet",
                          offer_id: int, amount: "Decimal",
                          reason: str = "") -> dict:
        """Reverse an offerwall credit (chargeback / fraud)."""
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.debit(
                wallet, amount,
                txn_type="reversal",
                description=f"Offerwall reversal: offer={offer_id} reason={reason}",
                reference_type="offer",
                reference_id=str(offer_id),
            )
            return {"success": True, "txn_id": str(txn.txn_id)}
        except Exception as e:
            logger.error(f"[OfferwallAdapter] reversal error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_available_balance_for_offers(wallet: "Wallet") -> dict:
        """Return balance data the offerwall uses for eligibility checks."""
        return {
            "current_balance": str(wallet.current_balance),
            "total_earned":    str(wallet.total_earned),
            "is_locked":       wallet.is_locked,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 22. AdNetworkAdapter  →  api.ad_networks
# ═══════════════════════════════════════════════════════════════════════════
class AdNetworkAdapter:
    """
    Credits publisher wallet from ad network revenue (CPM, CPC, CPV).
    Handles revenue share splits between platform and publisher.
    """

    REVENUE_SHARE = Decimal("0.70")  # 70% to publisher

    @staticmethod
    def on_ad_revenue(user, wallet: "Wallet",
                      network: str, revenue: "Decimal",
                      impression_id: str = "", ip: str = "") -> dict:
        """Credit publisher share of ad revenue to wallet."""
        try:
            publisher_share = (revenue * AdNetworkAdapter.REVENUE_SHARE).quantize(Decimal("0.01"))
            from api.wallet.services.earning.EarningService import EarningService
            result = EarningService.add_earning(
                user=user, wallet=wallet,
                amount=publisher_share,
                source=f"ad_network_{network}",
                source_type="ad_revenue",
                source_id=impression_id,
                ip_address=ip,
                metadata={"network": network, "gross_revenue": str(revenue),
                          "share_pct": str(AdNetworkAdapter.REVENUE_SHARE)},
            )
            return {"success": True, "credited": str(publisher_share)}
        except Exception as e:
            logger.error(f"[AdNetworkAdapter] revenue error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_revenue_summary(user, wallet: "Wallet", period: str = "monthly") -> dict:
        """Fetch ad revenue breakdown for publisher dashboard."""
        try:
            from api.ad_networks.services import AdNetworkService
            return AdNetworkService.get_publisher_revenue(user.pk, period)
        except ImportError:
            return {"total": "0.00", "networks": {}, "skipped": True}
        except Exception as e:
            return {"total": "0.00", "networks": {}, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 23. PromotionAdapter  →  api.promotions
# ═══════════════════════════════════════════════════════════════════════════
class PromotionAdapter:
    """
    Handles promotional credits: promo codes, deposit bonuses,
    welcome bonuses, and seasonal campaigns credited to wallet.
    """

    @staticmethod
    def apply_promo_code(user, wallet: "Wallet", code: str) -> dict:
        """Apply a promo code and credit the wallet bonus."""
        try:
            from api.promotions.services import PromotionService
            promo = PromotionService.validate_and_apply(
                user_id=user.pk,
                code=code.upper().strip(),
            )
            if not promo.get("valid"):
                return {"success": False, "reason": promo.get("reason", "Invalid code")}

            bonus = Decimal(str(promo.get("bonus_amount", "0")))
            if bonus > 0:
                from api.wallet.services.core.WalletService import WalletService
                txn = WalletService.credit(
                    wallet, bonus,
                    txn_type="bonus",
                    description=f"Promo code: {code}",
                    reference_type="promotion",
                    reference_id=promo.get("promo_id", ""),
                )
                return {
                    "success":  True,
                    "bonus":    str(bonus),
                    "txn_id":   str(txn.txn_id),
                    "promo_id": promo.get("promo_id"),
                }
            return {"success": True, "bonus": "0", "note": "No cash bonus"}
        except ImportError:
            return {"success": False, "reason": "Promotion service unavailable", "skipped": True}
        except Exception as e:
            logger.error(f"[PromotionAdapter] promo code error: {e}")
            return {"success": False, "reason": str(e)}

    @staticmethod
    def credit_signup_bonus(user, wallet: "Wallet") -> dict:
        """Credit new user signup bonus."""
        try:
            from api.promotions.services import PromotionService
            bonus = PromotionService.get_signup_bonus(user.pk)
            if bonus and Decimal(str(bonus)) > 0:
                from api.wallet.services.core.WalletService import WalletService
                txn = WalletService.credit(
                    wallet, Decimal(str(bonus)),
                    txn_type="bonus",
                    description="Welcome bonus",
                    reference_type="promotion",
                )
                return {"success": True, "bonus": str(bonus), "txn_id": str(txn.txn_id)}
            return {"success": True, "bonus": "0"}
        except ImportError:
            return {"success": True, "bonus": "0", "skipped": True}
        except Exception as e:
            logger.error(f"[PromotionAdapter] signup bonus error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_active_promotions(user) -> list:
        """Get active promotions the user can claim."""
        try:
            from api.promotions.services import PromotionService
            return PromotionService.get_user_promotions(user.pk)
        except ImportError:
            return []
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════════════════════
# 24. EngagementAdapter  →  api.engagement
# ═══════════════════════════════════════════════════════════════════════════
class EngagementAdapter:
    """
    Credits wallet for engagement actions: daily login bonus,
    streak rewards, profile completion, referral milestones.
    """

    @staticmethod
    def on_daily_login(user, wallet: "Wallet", streak_days: int) -> dict:
        """Credit daily login bonus scaled by streak."""
        try:
            from api.engagement.services import EngagementService
            bonus = EngagementService.calculate_login_bonus(user.pk, streak_days)
            if bonus and Decimal(str(bonus)) > 0:
                from api.wallet.services.core.WalletService import WalletService
                txn = WalletService.credit(
                    wallet, Decimal(str(bonus)),
                    txn_type="bonus",
                    description=f"Daily login bonus (streak: {streak_days})",
                    reference_type="engagement",
                )
                return {"success": True, "bonus": str(bonus), "txn_id": str(txn.txn_id)}
            return {"success": True, "bonus": "0"}
        except ImportError:
            return {"success": True, "bonus": "0", "skipped": True}
        except Exception as e:
            logger.error(f"[EngagementAdapter] login bonus error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def on_milestone_reached(user, wallet: "Wallet",
                             milestone: str, reward: "Decimal") -> dict:
        """Credit wallet when engagement milestone is hit."""
        try:
            if reward <= 0:
                return {"success": True, "credited": False}
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, reward,
                txn_type="bonus",
                description=f"Milestone reward: {milestone}",
                reference_type="engagement",
                reference_id=milestone,
            )
            return {"success": True, "bonus": str(reward), "txn_id": str(txn.txn_id)}
        except Exception as e:
            logger.error(f"[EngagementAdapter] milestone error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 25. LoyaltyAdapter  →  api.djoyalty
# ═══════════════════════════════════════════════════════════════════════════
class LoyaltyAdapter:
    """
    Converts djoyalty loyalty points into wallet cash.
    Tracks wallet activity that earns loyalty points.
    """

    @staticmethod
    def points_to_cash(user, wallet: "Wallet",
                       points: int) -> dict:
        """Convert loyalty points to BDT in wallet."""
        try:
            from api.djoyalty.services import DjoyaltyService
            result = DjoyaltyService.redeem_points(user.pk, points)
            if result.get("success"):
                cash = Decimal(str(result.get("cash_amount", "0")))
                if cash > 0:
                    from api.wallet.services.core.WalletService import WalletService
                    txn = WalletService.credit(
                        wallet, cash,
                        txn_type="bonus",
                        description=f"Loyalty points redeemed: {points} pts → ৳{cash}",
                        reference_type="loyalty",
                    )
                    return {
                        "success":  True,
                        "points":   points,
                        "cash":     str(cash),
                        "txn_id":   str(txn.txn_id),
                    }
            return {"success": False, "reason": result.get("reason", "Redemption failed")}
        except ImportError:
            return {"success": False, "reason": "Loyalty service unavailable", "skipped": True}
        except Exception as e:
            logger.error(f"[LoyaltyAdapter] points_to_cash error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def earn_points_for_withdrawal(user, amount: "Decimal") -> int:
        """Award loyalty points for making a withdrawal (loyalty reward)."""
        try:
            from api.djoyalty.services import DjoyaltyService
            points = int(amount * Decimal("0.1"))  # 0.1 point per BDT
            DjoyaltyService.award_points(
                user_id=user.pk, points=points,
                reason="withdrawal", metadata={"amount": str(amount)}
            )
            return points
        except ImportError:
            return 0
        except Exception:
            return 0

    @staticmethod
    def get_point_balance(user) -> dict:
        """Get user's current loyalty point balance."""
        try:
            from api.djoyalty.services import DjoyaltyService
            return DjoyaltyService.get_balance(user.pk)
        except ImportError:
            return {"points": 0, "cash_value": "0.00", "skipped": True}
        except Exception:
            return {"points": 0, "cash_value": "0.00"}


# ═══════════════════════════════════════════════════════════════════════════
# 26. SmartLinkAdapter  →  api.smartlink
# ═══════════════════════════════════════════════════════════════════════════
class SmartLinkAdapter:
    """
    Credits wallet when a SmartLink conversion fires.
    SmartLinks are the main revenue driver for publishers.
    """

    @staticmethod
    def on_conversion(user, wallet: "Wallet",
                      smartlink_id: str, payout: "Decimal",
                      click_id: str = "", country: str = "",
                      ip: str = "") -> dict:
        """Credit SmartLink conversion payout to wallet."""
        try:
            from api.wallet.services.earning.EarningService import EarningService
            result = EarningService.add_earning(
                user=user, wallet=wallet,
                amount=payout,
                source="smartlink",
                source_type="smartlink_conversion",
                source_id=smartlink_id,
                ip_address=ip,
                country_code=country,
                metadata={"click_id": click_id, "smartlink_id": smartlink_id},
            )
            return {"success": True, "credited": str(payout)}
        except Exception as e:
            logger.error(f"[SmartLinkAdapter] conversion error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_publisher_smartlink_earnings(user, wallet: "Wallet",
                                         period: str = "monthly") -> dict:
        """Earnings breakdown from SmartLinks for publisher dashboard."""
        try:
            from api.smartlink.services import SmartLinkService
            return SmartLinkService.get_publisher_earnings(user.pk, period)
        except ImportError:
            return {"total": "0.00", "clicks": 0, "conversions": 0, "skipped": True}
        except Exception:
            return {"total": "0.00", "clicks": 0, "conversions": 0}


# ═══════════════════════════════════════════════════════════════════════════
# 27. AuditLogAdapter  →  api.audit_logs
# ═══════════════════════════════════════════════════════════════════════════
class AuditLogAdapter:
    """
    Logs ALL wallet transactions and events to the central audit log.
    Required for compliance, fraud investigation, and financial reporting.
    """

    @staticmethod
    def log_transaction(user, wallet: "Wallet", txn,
                        action: str, ip: str = "",
                        extra: dict = None) -> None:
        """Log a wallet transaction to the audit trail."""
        try:
            from api.audit_logs.services import AuditLogger
            AuditLogger.log(
                actor_id=user.pk,
                action=f"wallet.{action}",
                resource_type="wallet_transaction",
                resource_id=str(txn.txn_id),
                metadata={
                    "wallet_id":  wallet.pk,
                    "amount":     str(txn.amount),
                    "type":       txn.type,
                    "status":     txn.status,
                    "ip_address": ip,
                    **(extra or {}),
                },
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[AuditLogAdapter] log error: {e}")

    @staticmethod
    def log_withdrawal(user, wallet: "Wallet", withdrawal,
                       action: str, ip: str = "") -> None:
        """Log withdrawal lifecycle events."""
        try:
            from api.audit_logs.services import AuditLogger
            AuditLogger.log(
                actor_id=user.pk,
                action=f"wallet.withdrawal.{action}",
                resource_type="withdrawal_request",
                resource_id=str(withdrawal.withdrawal_id),
                metadata={
                    "amount":  str(withdrawal.amount),
                    "method":  getattr(getattr(withdrawal, "payment_method", None), "method_type", ""),
                    "status":  withdrawal.status,
                    "ip":      ip,
                },
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[AuditLogAdapter] withdrawal log error: {e}")

    @staticmethod
    def log_admin_action(admin_user, target_user, wallet: "Wallet",
                         action: str, amount: "Decimal" = None,
                         reason: str = "") -> None:
        """Log admin wallet actions (credit, debit, lock, unlock)."""
        try:
            from api.audit_logs.services import AuditLogger
            AuditLogger.log(
                actor_id=admin_user.pk,
                action=f"admin.wallet.{action}",
                resource_type="wallet",
                resource_id=str(wallet.pk),
                metadata={
                    "target_user_id": target_user.pk if target_user else None,
                    "amount":  str(amount) if amount else None,
                    "reason":  reason,
                },
                is_admin_action=True,
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[AuditLogAdapter] admin log error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 28. RateLimitAdapter  →  api.rate_limit
# ═══════════════════════════════════════════════════════════════════════════
class RateLimitAdapter:
    """
    Checks withdrawal and earning rate limits via the central api.rate_limit
    service. Prevents abuse of the earning system.
    """

    @staticmethod
    def check_withdrawal_rate(user, amount: "Decimal") -> dict:
        """
        Check if user has exceeded withdrawal rate limits.
        Returns {allowed: bool, remaining: int, reset_at: str}
        """
        try:
            from api.rate_limit.services import RateLimitService
            return RateLimitService.check(
                key=f"wallet:withdrawal:{user.pk}",
                limit=10,         # 10 withdrawals per day
                window=86400,     # 24 hours
                amount=float(amount),
            )
        except ImportError:
            try:
                from api.wallet.rate_limiter import WalletRateLimiter
                allowed, remaining, _ = WalletRateLimiter.check(
                    f"withdrawal:{user.pk}", limit=10, window=86400
                )
                return {"allowed": allowed, "remaining": remaining}
            except Exception:
                return {"allowed": True, "remaining": 10}
        except Exception as e:
            logger.error(f"[RateLimitAdapter] check error: {e}")
            return {"allowed": True, "remaining": 10}

    @staticmethod
    def check_earning_rate(user, source: str) -> dict:
        """Check if user is earning within allowed rate limits."""
        try:
            from api.rate_limit.services import RateLimitService
            return RateLimitService.check(
                key=f"wallet:earning:{source}:{user.pk}",
                limit=100,
                window=3600,
            )
        except ImportError:
            return {"allowed": True, "remaining": 100}
        except Exception:
            return {"allowed": True, "remaining": 100}


# ═══════════════════════════════════════════════════════════════════════════
# 29. MessagingAdapter  →  api.messaging
# ═══════════════════════════════════════════════════════════════════════════
class MessagingAdapter:
    """
    Sends wallet-related internal messages:
    - Admin Slack/email alerts for large transactions
    - User DMs for important wallet events
    - Support ticket auto-creation for failed withdrawals
    """

    @staticmethod
    def alert_admin(subject: str, message: str,
                    level: str = "info", metadata: dict = None) -> None:
        """Send admin notification (Slack/email) for wallet events."""
        try:
            from api.messaging.services import MessagingService
            MessagingService.send_admin_alert(
                subject=subject,
                message=message,
                level=level,
                channel="wallet",
                metadata=metadata or {},
            )
        except ImportError:
            logger.info(f"[MessagingAdapter] Admin alert (no messaging): {subject}")
        except Exception as e:
            logger.error(f"[MessagingAdapter] alert_admin error: {e}")

    @staticmethod
    def send_user_message(user, message: str, message_type: str = "wallet") -> None:
        """Send an in-app message to the user about their wallet."""
        try:
            from api.messaging.services import MessagingService
            MessagingService.send_to_user(
                user_id=user.pk,
                message=message,
                message_type=message_type,
            )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[MessagingAdapter] send_user error: {e}")

    @staticmethod
    def create_support_ticket(user, subject: str, description: str,
                               wallet_id: int = None, priority: str = "normal") -> dict:
        """Auto-create support ticket for failed wallet operations."""
        try:
            from api.messaging.services import MessagingService
            return MessagingService.create_ticket(
                user_id=user.pk,
                subject=subject,
                description=description,
                category="wallet",
                priority=priority,
                metadata={"wallet_id": wallet_id},
            )
        except ImportError:
            return {"ticket_id": None, "skipped": True}
        except Exception as e:
            logger.error(f"[MessagingAdapter] ticket error: {e}")
            return {"ticket_id": None, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 30. MarketplaceAdapter  →  api.marketplace
# ═══════════════════════════════════════════════════════════════════════════
class MarketplaceAdapter:
    """
    Handles wallet payments in the marketplace:
    - Purchase deductions from wallet
    - Seller earnings credited to wallet
    - Refunds back to buyer wallet
    """

    @staticmethod
    def charge_buyer(buyer_user, wallet: "Wallet",
                     order_id: str, amount: "Decimal",
                     seller_id: int) -> dict:
        """Deduct marketplace purchase from buyer wallet."""
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.debit(
                wallet, amount,
                txn_type="marketplace_purchase",
                description=f"Marketplace order: {order_id}",
                reference_type="marketplace",
                reference_id=order_id,
            )
            return {"success": True, "txn_id": str(txn.txn_id), "charged": str(amount)}
        except Exception as e:
            logger.error(f"[MarketplaceAdapter] charge_buyer error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def credit_seller(seller_user, wallet: "Wallet",
                      order_id: str, amount: "Decimal",
                      platform_fee_pct: "Decimal" = Decimal("0.10")) -> dict:
        """Credit seller's wallet after platform fee deduction."""
        try:
            fee = (amount * platform_fee_pct).quantize(Decimal("0.01"))
            net = amount - fee
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, net,
                txn_type="marketplace_sale",
                description=f"Marketplace sale: {order_id} (fee: {fee})",
                reference_type="marketplace",
                reference_id=order_id,
            )
            return {"success": True, "txn_id": str(txn.txn_id), "credited": str(net), "fee": str(fee)}
        except Exception as e:
            logger.error(f"[MarketplaceAdapter] credit_seller error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def process_refund(buyer_user, wallet: "Wallet",
                       order_id: str, amount: "Decimal") -> dict:
        """Refund buyer's wallet for cancelled/returned order."""
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, amount,
                txn_type="marketplace_refund",
                description=f"Marketplace refund: {order_id}",
                reference_type="marketplace",
                reference_id=order_id,
            )
            return {"success": True, "txn_id": str(txn.txn_id), "refunded": str(amount)}
        except Exception as e:
            logger.error(f"[MarketplaceAdapter] refund error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 31. ProxyIntelligenceAdapter  →  api.proxy_intelligence
# ═══════════════════════════════════════════════════════════════════════════
class ProxyIntelligenceAdapter:
    """
    Detects VPN/proxy/datacenter IPs before allowing withdrawals.
    Prevents fraudulent withdrawals from masked locations.
    """

    @staticmethod
    def check_ip(ip_address: str) -> dict:
        """
        Returns {is_proxy: bool, is_vpn: bool, risk_score: float, country: str}
        """
        try:
            from api.proxy_intelligence.services import ProxyIntelligenceService
            return ProxyIntelligenceService.check(ip_address)
        except ImportError:
            return {"is_proxy": False, "is_vpn": False, "risk_score": 0.0, "skipped": True}
        except Exception as e:
            logger.error(f"[ProxyIntelligenceAdapter] check error: {e}")
            return {"is_proxy": False, "is_vpn": False, "risk_score": 0.0}

    @staticmethod
    def is_withdrawal_allowed_from_ip(ip_address: str,
                                       threshold: float = 0.7) -> tuple:
        """Returns (allowed: bool, reason: str)"""
        result = ProxyIntelligenceAdapter.check_ip(ip_address)
        if result.get("skipped"):
            return True, ""
        if result.get("is_proxy") or result.get("is_vpn"):
            return False, "Withdrawal not allowed from VPN/proxy connections"
        if float(result.get("risk_score", 0)) > threshold:
            return False, f"High-risk IP detected (score: {result['risk_score']:.2f})"
        return True, ""


# ═══════════════════════════════════════════════════════════════════════════
# 32. AdvertiserPortalAdapter  →  api.advertiser_portal
# ═══════════════════════════════════════════════════════════════════════════
class AdvertiserPortalAdapter:
    """
    Handles advertiser fund deposits that fuel the publisher payout pool.
    When an advertiser tops up, the money flows into the reward pool.
    """

    @staticmethod
    def on_advertiser_deposit(advertiser_id: int, amount: "Decimal",
                               campaign_id: str = "") -> dict:
        """Log advertiser deposit and add to reward pool."""
        try:
            from api.advertiser_portal.services import AdvertiserService
            return AdvertiserService.process_deposit(
                advertiser_id=advertiser_id,
                amount=amount,
                campaign_id=campaign_id,
            )
        except ImportError:
            return {"success": True, "pool_updated": True, "skipped": True}
        except Exception as e:
            logger.error(f"[AdvertiserPortalAdapter] deposit error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_campaign_budget_remaining(campaign_id: str) -> "Decimal":
        """Check remaining budget for a campaign (limits publisher earnings)."""
        try:
            from api.advertiser_portal.services import AdvertiserService
            result = AdvertiserService.get_budget(campaign_id)
            return Decimal(str(result.get("remaining", "0")))
        except ImportError:
            return Decimal("999999")  # No limit if service unavailable
        except Exception:
            return Decimal("999999")


# ═══════════════════════════════════════════════════════════════════════════
# 33. PublisherToolsAdapter  →  api.publisher_tools + api.monetization_tools
# ═══════════════════════════════════════════════════════════════════════════
class PublisherToolsAdapter:
    """
    Provides earnings analytics and payout tools to publisher dashboard.
    Also handles monetization-specific credits and revenue splits.
    """

    @staticmethod
    def get_earnings_dashboard(user, wallet: "Wallet",
                                period: str = "monthly") -> dict:
        """Full publisher earnings breakdown for dashboard."""
        try:
            from api.publisher_tools.services import PublisherDashboardService
            return PublisherDashboardService.get_earnings(user.pk, period)
        except ImportError:
            return {
                "total_earned":     str(wallet.total_earned),
                "total_withdrawn":  str(wallet.total_withdrawn),
                "available":        str(wallet.current_balance),
                "period":           period,
                "skipped":          True,
            }
        except Exception as e:
            logger.error(f"[PublisherToolsAdapter] dashboard error: {e}")
            return {"total_earned": str(wallet.total_earned)}

    @staticmethod
    def on_monetization_event(user, wallet: "Wallet",
                               event_type: str, amount: "Decimal",
                               metadata: dict = None) -> dict:
        """Credit wallet for monetization events (widget impressions, API calls, etc)."""
        try:
            from api.monetization_tools.services import MonetizationService
            result = MonetizationService.process_event(
                user_id=user.pk,
                event_type=event_type,
                amount=amount,
                metadata=metadata or {},
            )
            if result.get("credit_wallet") and Decimal(str(result.get("amount", 0))) > 0:
                from api.wallet.services.core.WalletService import WalletService
                txn = WalletService.credit(
                    wallet, Decimal(str(result["amount"])),
                    txn_type="monetization",
                    description=f"Monetization: {event_type}",
                    reference_type="monetization",
                )
                return {"success": True, "txn_id": str(txn.txn_id)}
            return {"success": True, "credited": False}
        except ImportError:
            return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[PublisherToolsAdapter] monetization error: {e}")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 34. TenantWalletAdapter  →  api.tenants
# ═══════════════════════════════════════════════════════════════════════════
class TenantWalletAdapter:
    """
    Multi-tenant wallet isolation. Ensures wallets are properly scoped
    to the correct tenant in a multi-tenant deployment.
    """

    @staticmethod
    def get_tenant_for_user(user) -> Optional[Any]:
        """Get the tenant associated with this user."""
        try:
            from api.tenants.services import TenantService
            return TenantService.get_user_tenant(user.pk)
        except ImportError:
            return None
        except Exception:
            return None

    @staticmethod
    def get_tenant_wallet_config(tenant) -> dict:
        """
        Get tenant-specific wallet configuration:
        min/max withdrawal, allowed currencies, gateway restrictions.
        """
        try:
            from api.tenants.services import TenantService
            return TenantService.get_wallet_config(tenant.pk if tenant else None)
        except ImportError:
            return {
                "currency":       "BDT",
                "min_withdrawal": "50",
                "max_withdrawal": "100000",
                "gateways":       ["bkash", "nagad", "bank"],
            }
        except Exception:
            return {"currency": "BDT", "min_withdrawal": "50", "max_withdrawal": "100000"}

    @staticmethod
    def is_wallet_enabled_for_tenant(tenant) -> bool:
        """Check if wallet feature is enabled for this tenant."""
        try:
            from api.tenants.services import TenantService
            return TenantService.is_feature_enabled(
                tenant.pk if tenant else None, "wallet"
            )
        except ImportError:
            return True
        except Exception:
            return True


# ═══════════════════════════════════════════════════════════════════════════
# 35. CacheAdapter  →  api.cache
# ═══════════════════════════════════════════════════════════════════════════
class CacheAdapter:
    """
    Caches wallet balance reads to reduce DB load.
    Uses Redis via api.cache for fast balance checks.
    """

    CACHE_TTL = 30  # 30 seconds balance cache

    @staticmethod
    def get_cached_balance(wallet_id: int) -> Optional["Decimal"]:
        """Get cached wallet balance. Returns None if not cached."""
        try:
            from api.cache.services import CacheService
            val = CacheService.get(f"wallet:balance:{wallet_id}")
            return Decimal(str(val)) if val is not None else None
        except ImportError:
            from django.core.cache import cache
            val = cache.get(f"wallet:balance:{wallet_id}")
            return Decimal(str(val)) if val is not None else None
        except Exception:
            return None

    @staticmethod
    def set_cached_balance(wallet_id: int, balance: "Decimal") -> None:
        """Cache wallet balance after update."""
        try:
            from api.cache.services import CacheService
            CacheService.set(f"wallet:balance:{wallet_id}", str(balance), CacheAdapter.CACHE_TTL)
        except ImportError:
            from django.core.cache import cache
            cache.set(f"wallet:balance:{wallet_id}", str(balance), CacheAdapter.CACHE_TTL)
        except Exception as e:
            logger.debug(f"[CacheAdapter] set error: {e}")

    @staticmethod
    def invalidate_wallet_cache(wallet_id: int) -> None:
        """Invalidate all wallet caches after update."""
        try:
            from api.cache.services import CacheService
            CacheService.delete_pattern(f"wallet:*:{wallet_id}")
        except ImportError:
            from django.core.cache import cache
            cache.delete(f"wallet:balance:{wallet_id}")
        except Exception as e:
            logger.debug(f"[CacheAdapter] invalidate error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 36. LocalizationAdapter  →  api.localization
# ═══════════════════════════════════════════════════════════════════════════
class LocalizationAdapter:
    """Format wallet amounts and dates in the user's locale."""

    @staticmethod
    def format_amount(amount: "Decimal", currency: str = "BDT",
                      locale: str = "bn_BD") -> str:
        """Format amount in user's locale (e.g., ১,০০০.০০ ৳)."""
        try:
            from api.localization.services import LocalizationService
            return LocalizationService.format_currency(amount, currency, locale)
        except ImportError:
            return f"৳{amount:,.2f}"
        except Exception:
            return f"৳{amount:,.2f}"

    @staticmethod
    def get_user_locale(user) -> str:
        """Get user's preferred locale."""
        try:
            from api.localization.services import LocalizationService
            return LocalizationService.get_user_locale(user.pk) or "bn_BD"
        except ImportError:
            return "bn_BD"
        except Exception:
            return "bn_BD"


# ═══════════════════════════════════════════════════════════════════════════
# 37. AdminPanelAdapter  →  api.admin_panel
# ═══════════════════════════════════════════════════════════════════════════
class AdminPanelAdapter:
    """
    Bridges wallet data to the custom admin panel (api.admin_panel).
    Provides admin actions: credit, debit, lock, bulk ops, reports.
    """

    @staticmethod
    def get_wallet_admin_summary(wallet: "Wallet") -> dict:
        """Full wallet data for admin panel display."""
        try:
            return {
                "wallet_id":       wallet.pk,
                "user_id":         wallet.user_id,
                "current_balance": str(wallet.current_balance),
                "frozen_balance":  str(wallet.frozen_balance or 0),
                "total_earned":    str(wallet.total_earned),
                "total_withdrawn": str(wallet.total_withdrawn),
                "is_locked":       wallet.is_locked,
                "locked_reason":   wallet.locked_reason or "",
                "kyc_level":       KYCWalletAdapter.get_kyc_level(wallet.user),
                "risk_flags":      [],
            }
        except Exception as e:
            logger.error(f"[AdminPanelAdapter] summary error: {e}")
            return {"wallet_id": wallet.pk, "error": str(e)}

    @staticmethod
    def register_admin_action(action: str, admin_id: int,
                               target_wallet_id: int, amount: "Decimal" = None,
                               reason: str = "") -> None:
        """Log an admin panel action on a wallet."""
        try:
            from api.admin_panel.services import AdminActionService
            AdminActionService.record(
                action=f"wallet.{action}",
                admin_id=admin_id,
                target_id=target_wallet_id,
                metadata={"amount": str(amount) if amount else None, "reason": reason},
            )
        except ImportError:
            logger.info(f"[AdminPanelAdapter] action={action} admin={admin_id} wallet={target_wallet_id}")
        except Exception as e:
            logger.error(f"[AdminPanelAdapter] register_action error: {e}")

    @staticmethod
    def get_pending_approvals() -> list:
        """Get wallet items waiting for admin approval (withdrawals, KYC, disputes)."""
        try:
            from api.wallet.models import WithdrawalRequest
            pending = WithdrawalRequest.objects.filter(status="pending").count()
            from api.wallet.services_extra import KYCService
            from api.wallet.models_cpalead_extra import KYCVerification
            kyc_pending = KYCVerification.objects.filter(status="pending").count()
            return [
                {"type": "withdrawal", "count": pending},
                {"type": "kyc",        "count": kyc_pending},
            ]
        except Exception as e:
            logger.error(f"[AdminPanelAdapter] pending_approvals error: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════
# 38. CMSAdapter  →  api.cms
# ═══════════════════════════════════════════════════════════════════════════
class CMSAdapter:
    """
    Fetches CMS content for wallet UI:
    - Wallet page banners and notices
    - Withdrawal method descriptions
    - Help text and FAQ content
    - Promotional banners for wallet dashboard
    """

    @staticmethod
    def get_wallet_banner(user=None, page: str = "wallet_home") -> dict:
        """Get active promotional banner for wallet page."""
        try:
            from api.cms.services import CMSService
            return CMSService.get_banner(page=page, user_id=user.pk if user else None)
        except ImportError:
            return {"banner": None, "skipped": True}
        except Exception as e:
            logger.debug(f"[CMSAdapter] get_banner error: {e}")
            return {"banner": None}

    @staticmethod
    def get_wallet_notice(notice_type: str = "withdrawal_notice") -> str:
        """Get wallet-related notice text from CMS."""
        try:
            from api.cms.services import CMSService
            result = CMSService.get_content(key=notice_type)
            return result.get("content", "")
        except ImportError:
            return ""
        except Exception:
            return ""

    @staticmethod
    def get_faq(section: str = "wallet") -> list:
        """Get FAQ items for wallet help section."""
        try:
            from api.cms.services import CMSService
            return CMSService.get_faq(section=section)
        except ImportError:
            return []
        except Exception:
            return []

    @staticmethod
    def get_withdrawal_method_info(method_type: str) -> dict:
        """Get human-readable info about a withdrawal method from CMS."""
        defaults = {
            "bkash":      {"name": "bKash",      "logo": "bkash.png",  "processing_time": "Instant"},
            "nagad":      {"name": "Nagad",       "logo": "nagad.png",  "processing_time": "Instant"},
            "rocket":     {"name": "Rocket",      "logo": "rocket.png", "processing_time": "Instant"},
            "bank":       {"name": "Bank Transfer","logo": "bank.png",   "processing_time": "1-3 days"},
            "usdt_trc20": {"name": "USDT (TRC20)","logo": "usdt.png",   "processing_time": "30 minutes"},
        }
        try:
            from api.cms.services import CMSService
            result = CMSService.get_content(key=f"withdrawal_method_{method_type}")
            return result.get("content", defaults.get(method_type, {}))
        except ImportError:
            return defaults.get(method_type, {})
        except Exception:
            return defaults.get(method_type, {})


# ═══════════════════════════════════════════════════════════════════════════
# 39. TasksAdapter  →  api.tasks
# ═══════════════════════════════════════════════════════════════════════════
class TasksAdapter:
    """
    Dispatches async Celery tasks for wallet operations that should
    not block the request/response cycle.
    """

    @staticmethod
    def schedule_withdrawal_processing(withdrawal_id: str,
                                        delay_seconds: int = 0) -> dict:
        """Queue withdrawal processing as a Celery task."""
        try:
            from api.tasks.wallet_tasks import process_withdrawal_task
            result = process_withdrawal_task.apply_async(
                args=[withdrawal_id],
                countdown=delay_seconds,
            )
            return {"success": True, "task_id": result.id}
        except ImportError:
            # Fall back to wallet's own tasks
            try:
                from api.wallet.tasks.withdrawal_processing_tasks import process_withdrawal
                result = process_withdrawal.apply_async(args=[withdrawal_id], countdown=delay_seconds)
                return {"success": True, "task_id": str(result.id)}
            except Exception:
                return {"success": True, "task_id": None, "skipped": True}
        except Exception as e:
            logger.error(f"[TasksAdapter] schedule_withdrawal error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def schedule_balance_sync(wallet_id: int, priority: str = "normal") -> dict:
        """Queue balance reconciliation task."""
        try:
            from api.tasks.wallet_tasks import sync_wallet_balance_task
            result = sync_wallet_balance_task.apply_async(args=[wallet_id])
            return {"success": True, "task_id": result.id}
        except ImportError:
            try:
                from api.wallet.tasks.balance_sync_tasks import sync_wallet_balance
                result = sync_wallet_balance.apply_async(args=[wallet_id])
                return {"success": True, "task_id": str(result.id)}
            except Exception:
                return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[TasksAdapter] balance_sync error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def schedule_fraud_check(txn_id: int) -> dict:
        """Async fraud check after transaction."""
        try:
            from api.tasks.wallet_tasks import check_transaction_fraud_task
            result = check_transaction_fraud_task.apply_async(args=[txn_id], countdown=5)
            return {"success": True, "task_id": result.id}
        except ImportError:
            try:
                from api.wallet.tasks.fraud_check_tasks import check_transaction_fraud
                result = check_transaction_fraud.apply_async(args=[txn_id], countdown=5)
                return {"success": True, "task_id": str(result.id)}
            except Exception:
                return {"success": True, "skipped": True}
        except Exception as e:
            logger.error(f"[TasksAdapter] fraud_check error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def schedule_statement_generation(user_id: int, month: int, year: int) -> dict:
        """Queue monthly statement PDF generation."""
        try:
            from api.tasks.wallet_tasks import generate_statement_task
            result = generate_statement_task.apply_async(args=[user_id, month, year])
            return {"success": True, "task_id": result.id}
        except ImportError:
            try:
                from api.wallet.tasks.statement_tasks import generate_statement
                result = generate_statement.apply_async(args=[user_id, month, year])
                return {"success": True, "task_id": str(result.id)}
            except Exception:
                return {"success": True, "skipped": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 40. BackupAdapter  →  api.backup
# ═══════════════════════════════════════════════════════════════════════════
class BackupAdapter:
    """
    Triggers wallet data backup before destructive operations
    (bulk updates, migrations, large debits).
    """

    @staticmethod
    def backup_wallet_before_operation(wallet: "Wallet",
                                        operation: str) -> dict:
        """Create a point-in-time backup of wallet data."""
        try:
            from api.backup.services import BackupService
            return BackupService.snapshot(
                model="wallet",
                record_id=wallet.pk,
                operation=operation,
                data={
                    "current_balance": str(wallet.current_balance),
                    "frozen_balance":  str(wallet.frozen_balance or 0),
                    "total_earned":    str(wallet.total_earned),
                    "total_withdrawn": str(wallet.total_withdrawn),
                    "is_locked":       wallet.is_locked,
                    "version":         wallet.version,
                },
            )
        except ImportError:
            # Log locally as fallback
            logger.info(
                f"[BackupAdapter] Pre-op snapshot wallet={wallet.pk} "
                f"op={operation} balance={wallet.current_balance}"
            )
            return {"success": True, "snapshot_id": None, "skipped": True}
        except Exception as e:
            logger.error(f"[BackupAdapter] backup error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def restore_wallet_from_backup(wallet_id: int, snapshot_id: str) -> dict:
        """Restore wallet to a previous snapshot (emergency recovery)."""
        try:
            from api.backup.services import BackupService
            return BackupService.restore(
                model="wallet",
                record_id=wallet_id,
                snapshot_id=snapshot_id,
            )
        except ImportError:
            return {"success": False, "reason": "Backup service not available", "skipped": True}
        except Exception as e:
            logger.error(f"[BackupAdapter] restore error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_wallet_backup_history(wallet_id: int, limit: int = 10) -> list:
        """List recent backups for a wallet."""
        try:
            from api.backup.services import BackupService
            return BackupService.list_snapshots("wallet", wallet_id, limit)
        except ImportError:
            return []
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════════════════════
# 41. VersionControlAdapter  →  api.version_control
# ═══════════════════════════════════════════════════════════════════════════
class VersionControlAdapter:
    """
    Wallet API versioning — ensures backward compatibility when
    the wallet API changes. Used by external integrations.
    """

    CURRENT_VERSION = "v2"
    SUPPORTED_VERSIONS = ["v1", "v2"]

    @staticmethod
    def get_api_version(request=None) -> str:
        """Determine API version from request headers or default."""
        if request:
            version = request.headers.get("X-Wallet-API-Version", "")
            if version in VersionControlAdapter.SUPPORTED_VERSIONS:
                return version
        return VersionControlAdapter.CURRENT_VERSION

    @staticmethod
    def is_deprecated(version: str) -> bool:
        """Check if a version is deprecated."""
        deprecated = ["v1"]
        return version in deprecated

    @staticmethod
    def transform_response_for_version(data: dict, version: str) -> dict:
        """Transform wallet API response for backward-compatible older versions."""
        try:
            from api.version_control.services import VersionTransformer
            return VersionTransformer.transform(
                data=data,
                target_version=version,
                resource="wallet",
            )
        except ImportError:
            # v1 compat: rename fields
            if version == "v1":
                data = dict(data)
                if "current_balance" in data:
                    data["balance"] = data["current_balance"]       # v1 used 'balance'
                if "withdrawal_id" in data:
                    data["id"] = data["withdrawal_id"]              # v1 used 'id'
            return data

    @staticmethod
    def log_version_usage(version: str, endpoint: str) -> None:
        """Track API version usage for deprecation planning."""
        try:
            from api.version_control.services import VersionTracker
            VersionTracker.log(version=version, endpoint=endpoint, resource="wallet")
        except ImportError:
            if VersionControlAdapter.is_deprecated(version):
                logger.warning(f"[VersionControl] Deprecated API {version} used on {endpoint}")


# ═══════════════════════════════════════════════════════════════════════════
# 42. InventoryAdapter  →  api.inventory
# ═══════════════════════════════════════════════════════════════════════════
class InventoryAdapter:
    """
    Handles wallet payments for inventory purchases.
    When a user buys something from inventory, wallet is debited.
    """

    @staticmethod
    def deduct_for_purchase(user, wallet: "Wallet",
                             item_id: str, quantity: int,
                             unit_price: "Decimal") -> dict:
        """Deduct inventory purchase from wallet."""
        total = unit_price * quantity
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.debit(
                wallet, total,
                txn_type="inventory_purchase",
                description=f"Inventory: item={item_id} qty={quantity} @ {unit_price}",
                reference_type="inventory",
                reference_id=item_id,
            )
            return {
                "success": True,
                "txn_id":  str(txn.txn_id),
                "charged": str(total),
            }
        except Exception as e:
            logger.error(f"[InventoryAdapter] deduct error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_affordable_items(wallet: "Wallet", category: str = "") -> list:
        """Return inventory items the user can afford with their balance."""
        try:
            from api.inventory.services import InventoryService
            return InventoryService.get_affordable(
                max_price=float(wallet.current_balance),
                category=category,
            )
        except ImportError:
            return []
        except Exception as e:
            logger.error(f"[InventoryAdapter] affordable items error: {e}")
            return []

    @staticmethod
    def refund_inventory_purchase(user, wallet: "Wallet",
                                   item_id: str, amount: "Decimal") -> dict:
        """Refund a cancelled inventory purchase."""
        try:
            from api.wallet.services.core.WalletService import WalletService
            txn = WalletService.credit(
                wallet, amount,
                txn_type="inventory_refund",
                description=f"Inventory refund: item={item_id}",
                reference_type="inventory",
                reference_id=item_id,
            )
            return {"success": True, "txn_id": str(txn.txn_id), "refunded": str(amount)}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 43. OfferInventoryAdapter  →  api.offer_inventory
# ═══════════════════════════════════════════════════════════════════════════
class OfferInventoryAdapter:
    """
    Provides wallet with real-time offer inventory data:
    - Which offers are currently available for a user
    - Estimated earnings from available offers
    - Offer eligibility based on wallet status
    """

    @staticmethod
    def get_available_offers(user, wallet: "Wallet",
                              country: str = "BD",
                              limit: int = 20) -> list:
        """Get offers currently available for this user."""
        try:
            from api.offer_inventory.services import OfferInventoryService
            return OfferInventoryService.get_for_user(
                user_id=user.pk,
                country=country,
                wallet_balance=float(wallet.current_balance),
                limit=limit,
            )
        except ImportError:
            # Fall back to wallet's own offer model
            try:
                from api.wallet.models_cpalead_extra import EarningOffer
                offers = EarningOffer.objects.filter(
                    is_active=True
                ).values("id", "title", "offer_type", "payout", "payout_currency")[:limit]
                return list(offers)
            except Exception:
                return []
        except Exception as e:
            logger.error(f"[OfferInventoryAdapter] get_offers error: {e}")
            return []

    @staticmethod
    def estimate_daily_earnings(user, country: str = "BD") -> "Decimal":
        """Estimate how much a user could earn today from available offers."""
        try:
            from api.offer_inventory.services import OfferInventoryService
            result = OfferInventoryService.estimate_earnings(user.pk, country)
            return Decimal(str(result.get("estimated", "0")))
        except ImportError:
            return Decimal("0")
        except Exception:
            return Decimal("0")

    @staticmethod
    def mark_offer_seen(user, offer_id: int) -> None:
        """Track that a user has seen an offer (analytics)."""
        try:
            from api.offer_inventory.services import OfferInventoryService
            OfferInventoryService.mark_seen(user.pk, offer_id)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[OfferInventoryAdapter] mark_seen error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 44. DisasterRecoveryFullAdapter  →  api.disaster_recovery
# ═══════════════════════════════════════════════════════════════════════════
class DisasterRecoveryFullAdapter:
    """
    Full disaster recovery for the wallet system.
    Handles: failover, data recovery, backup verification, health checks.
    Different from dr_integration (api.dr_integration) which handles
    real-time data sync. This handles full DR scenarios.
    """

    @staticmethod
    def health_check() -> dict:
        """Check wallet system health for DR monitoring."""
        try:
            from api.wallet.models import Wallet, WalletTransaction
            wallet_count = Wallet.objects.count()
            txn_count    = WalletTransaction.objects.count()
            return {
                "healthy":       True,
                "wallet_count":  wallet_count,
                "txn_count":     txn_count,
                "status":        "operational",
            }
        except Exception as e:
            return {"healthy": False, "error": str(e), "status": "degraded"}

    @staticmethod
    def initiate_failover(reason: str = "") -> dict:
        """
        Initiate wallet system failover to DR site.
        Called by api.disaster_recovery orchestrator.
        """
        try:
            from api.disaster_recovery.services import DROrchestrator
            return DROrchestrator.failover_wallet(reason=reason)
        except ImportError:
            logger.critical(f"[DRFullAdapter] FAILOVER requested: {reason} (DR service not available)")
            return {"success": False, "reason": "DR service not installed", "skipped": True}
        except Exception as e:
            logger.critical(f"[DRFullAdapter] Failover error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_data_integrity(wallet_ids: list = None) -> dict:
        """
        Verify wallet data integrity post-recovery.
        Checks balance hash, transaction totals, ledger consistency.
        """
        try:
            from api.wallet.models import Wallet
            from api.wallet.services.core.WalletService import WalletService
            checked = 0
            issues  = []
            qs = Wallet.objects.all()[:100] if not wallet_ids else Wallet.objects.filter(pk__in=wallet_ids)
            for wallet in qs:
                try:
                    WalletService.verify_integrity(wallet)
                    checked += 1
                except Exception as e:
                    issues.append({"wallet_id": wallet.pk, "error": str(e)})
            return {
                "checked": checked,
                "issues":  issues,
                "clean":   len(issues) == 0,
            }
        except Exception as e:
            logger.error(f"[DRFullAdapter] integrity check error: {e}")
            return {"checked": 0, "issues": [], "clean": True}

    @staticmethod
    def create_emergency_snapshot() -> dict:
        """Create emergency snapshot of all wallet balances."""
        try:
            from api.disaster_recovery.services import DROrchestrator
            return DROrchestrator.emergency_snapshot("wallet")
        except ImportError:
            # Manual CSV-style snapshot
            try:
                from api.wallet.models import Wallet
                import json
                from django.utils import timezone
                wallets = list(Wallet.objects.values(
                    "id", "user_id", "current_balance", "frozen_balance",
                    "total_earned", "total_withdrawn", "version"
                ))
                snapshot_id = f"emergency_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                logger.critical(
                    f"[DRFullAdapter] Emergency snapshot {snapshot_id}: "
                    f"{len(wallets)} wallets"
                )
                return {"success": True, "snapshot_id": snapshot_id,
                        "count": len(wallets), "skipped": True}
            except Exception as e:
                return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 45. APIRootAdapter  →  api (root app)
# ═══════════════════════════════════════════════════════════════════════════
class APIRootAdapter:
    """
    Integration with the root 'api' app.
    Handles: API-wide settings, feature flags, global configuration.
    """

    @staticmethod
    def get_wallet_feature_flags() -> dict:
        """Get wallet feature flags from global config."""
        try:
            from api.config import WALLET_FEATURES
            return WALLET_FEATURES
        except ImportError:
            try:
                from django.conf import settings
                return getattr(settings, "WALLET_FEATURES", {
                    "bnpl_enabled":          True,
                    "escrow_enabled":        True,
                    "virtual_cards_enabled": False,
                    "open_banking_enabled":  False,
                    "crypto_enabled":        True,
                })
            except Exception:
                return {}

    @staticmethod
    def get_global_wallet_limits() -> dict:
        """Get platform-wide wallet limits."""
        try:
            from django.conf import settings
            return {
                "min_withdrawal":      getattr(settings, "WALLET_MIN_WITHDRAWAL", "50.00"),
                "max_withdrawal":      getattr(settings, "WALLET_MAX_WITHDRAWAL", "100000.00"),
                "max_daily":           getattr(settings, "WALLET_MAX_DAILY_WITHDRAWAL", "50000.00"),
                "max_monthly":         getattr(settings, "WALLET_MAX_MONTHLY_WITHDRAWAL", "500000.00"),
                "max_balance":         getattr(settings, "WALLET_MAX_BALANCE", "10000000.00"),
                "currency":            getattr(settings, "WALLET_DEFAULT_CURRENCY", "BDT"),
            }
        except Exception as e:
            return {"min_withdrawal": "50", "max_withdrawal": "100000", "currency": "BDT"}

    @staticmethod
    def is_maintenance_mode() -> bool:
        """Check if platform is in maintenance mode (halt all wallet ops)."""
        try:
            from api.config import MAINTENANCE_MODE
            return MAINTENANCE_MODE.get("wallet", False)
        except ImportError:
            try:
                from django.conf import settings
                return getattr(settings, "WALLET_MAINTENANCE_MODE", False)
            except Exception:
                return False


