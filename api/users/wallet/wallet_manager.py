"""
api/users/wallet/wallet_manager.py
Wallet BRIDGE — users app api.wallet-কে call করে।
নিজে wallet logic করে না।
শুধু user context থেকে wallet data access করার shortcut।
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class UserWalletBridge:
    """
    users app-এ wallet data দরকার হলে এই class use করো।
    api.wallet-এর model সরাসরি import করো না views-এ।
    এই bridge সব handle করবে।
    """

    # ─────────────────────────────────────
    # READ
    # ─────────────────────────────────────
    def get_balance(self, user) -> dict:
        """
        User-এর wallet balance দাও।
        Cache থেকে নাও, না থাকলে api.wallet DB থেকে।
        """
        from ..cache import user_cache

        cached = user_cache.get_balance(str(user.id))
        if cached is not None:
            return {
                'balance':          cached,
                'available_balance': cached,
                'currency':         'USD',
            }

        wallet = self._get_wallet(user)
        if not wallet:
            return {
                'balance':          float(getattr(user, 'balance', 0)),
                'available_balance': float(getattr(user, 'balance', 0)),
                'currency':         'USD',
            }

        balance = float(getattr(wallet, 'balance', 0) or 0)
        user_cache.set_balance(str(user.id), balance)

        return {
            'balance':             balance,
            'available_balance':   float(getattr(wallet, 'available_balance', balance) or balance),
            'pending_balance':     float(getattr(wallet, 'pending_balance', 0) or 0),
            'total_earned':        float(getattr(wallet, 'total_earned', 0) or 0),
            'total_withdrawn':     float(getattr(wallet, 'total_withdrawn', 0) or 0),
            'currency':            getattr(wallet, 'currency', 'USD'),
        }

    def get_transaction_summary(self, user, days: int = 30) -> dict:
        """Last N days-এর transaction summary"""
        try:
            from django.apps import apps
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Sum, Count, Q

            Transaction = apps.get_model('wallet', 'Transaction')
            since       = timezone.now() - timedelta(days=days)

            qs = Transaction.objects.filter(user=user, created_at__gte=since)

            return {
                'total_credits':     float(qs.filter(type='credit').aggregate(s=Sum('amount'))['s'] or 0),
                'total_debits':      float(qs.filter(type='debit').aggregate(s=Sum('amount'))['s'] or 0),
                'transaction_count': qs.count(),
                'period_days':       days,
            }
        except Exception as e:
            logger.warning(f'Transaction summary failed: {e}')
            return {}

    def get_recent_transactions(self, user, limit: int = 10) -> list:
        """Recent transactions list"""
        try:
            from django.apps import apps
            Transaction = apps.get_model('wallet', 'Transaction')
            return list(
                Transaction.objects.filter(user=user)
                .order_by('-created_at')
                .values(
                    'id', 'type', 'amount', 'description',
                    'status', 'created_at'
                )[:limit]
            )
        except Exception as e:
            logger.warning(f'Recent transactions failed: {e}')
            return []

    # ─────────────────────────────────────
    # CREDIT (offer complete হলে)
    # ─────────────────────────────────────
    def credit(self, user, amount: Decimal, description: str, reference: str = '') -> bool:
        """
        User-এর wallet-এ credit করো।
        api.wallet-এর service call করো।
        """
        try:
            from django.apps import apps
            # api.wallet-এর service use করো
            try:
                WalletService = apps.get_model('wallet', 'Wallet')
                wallet = WalletService.objects.get(user=user)
                wallet.balance += amount
                wallet.total_earned += amount
                wallet.save(update_fields=['balance', 'total_earned'])
            except Exception:
                # Fallback: user model-এ
                user.balance = (getattr(user, 'balance', 0) or 0) + float(amount)
                user.total_earned = (getattr(user, 'total_earned', 0) or 0) + float(amount)
                user.save(update_fields=['balance', 'total_earned'])

            # Cache invalidate
            from ..cache import user_cache
            user_cache.invalidate_balance(str(user.id))

            # Tier check করো (upgrade হতে পারে)
            self._check_tier_upgrade(user)

            logger.info(f'Wallet credited: ${amount} for user {user.id}')
            return True

        except Exception as e:
            logger.error(f'Wallet credit failed for user {user.id}: {e}')
            return False

    # ─────────────────────────────────────
    # TIER UPGRADE CHECK
    # ─────────────────────────────────────
    def _check_tier_upgrade(self, user) -> None:
        """
        Total earned বাড়লে tier upgrade check করো।
        api.wallet credit হওয়ার পরে call হয়।
        """
        try:
            from ..constants import UserTier
            total_earned = float(getattr(user, 'total_earned', 0) or 0)
            current_tier = getattr(user, 'tier', 'FREE')

            new_tier = current_tier
            for tier, threshold in sorted(
                UserTier.THRESHOLDS.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                if total_earned >= threshold:
                    new_tier = tier
                    break

            if new_tier != current_tier:
                user.tier = new_tier
                user.save(update_fields=['tier'])

                # Cache update
                from ..cache import user_cache
                user_cache.set_tier(str(user.id), new_tier)

                # Gamification signal
                from ..profile.achievement_manager import achievement_manager
                achievement_manager.check_tier_achievement(user, new_tier)

                # Gamification earning milestone check
                achievement_manager.check_earning_milestone(user, total_earned)

                logger.info(f'Tier upgraded: {current_tier} → {new_tier} for user {user.id}')

        except Exception as e:
            logger.warning(f'Tier upgrade check failed: {e}')

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _get_wallet(self, user):
        try:
            from django.apps import apps
            Wallet = apps.get_model('wallet', 'Wallet')
            return Wallet.objects.get(user=user)
        except Exception:
            return None


# Singleton
wallet_bridge = UserWalletBridge()
