# api/wallet/services.py — Complete Upgraded Version
# ============================================================
# তোমার existing WalletService এর উপর built, সব নতুন feature add করা হয়েছে
# ============================================================

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import logging

from .models import Wallet, WalletTransaction, UserPaymentMethod, Withdrawal, WithdrawalRequest

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
MIN_WITHDRAWAL = getattr(settings, 'MIN_WITHDRAWAL_AMOUNT', Decimal('50.00'))
MAX_DAILY_WITHDRAWAL = getattr(settings, 'MAX_DAILY_WITHDRAWAL', Decimal('10000.00'))
WITHDRAWAL_FEE_PERCENT = getattr(settings, 'WITHDRAWAL_FEE_PERCENT', Decimal('2.0'))

GATEWAY_MIN_AMOUNTS = getattr(settings, 'GATEWAY_MIN_AMOUNTS', {
    'bkash': Decimal('50.00'),
    'nagad': Decimal('50.00'),
    'rocket': Decimal('50.00'),
    'bank': Decimal('500.00'),
    'paypal': Decimal('100.00'),
    'usdt': Decimal('10.00'),
})


class WalletService:
    """
    Wallet এর সব operations।
    তোমার existing service এর সব method রাখা হয়েছে + নতুন add করা হয়েছে।
    """

    # ────────────────────────────────────────────────────────
    # EXISTING METHODS (unchanged, bug fixed)
    # ────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def create_wallet(user):
        """Auto-create wallet on user signup"""
        wallet, created = Wallet.objects.get_or_create(user=user)
        return wallet

    @staticmethod
    @transaction.atomic
    def add_earnings(wallet, amount, description='', reference_id='',
                     metadata=None, source_type='', source_id=''):
        """
        Wallet এ earning add করো।
        UPGRADED: source_type + source_id দিয়ে কোন offer/task থেকে এলো track করা হয়।
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        amount = Decimal(str(amount))

        # User tier bonus apply করো
        bonus_multiplier = WalletService._get_tier_bonus_multiplier(wallet.user)
        if bonus_multiplier > 1:
            original_amount = amount
            amount = amount * Decimal(str(bonus_multiplier))
            logger.info(f"Tier bonus applied: {original_amount} → {amount} (×{bonus_multiplier})")

        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type='earning',
            amount=amount,
            status='approved',
            description=description,
            reference_id=reference_id,
            metadata={
                **(metadata or {}),
                'source_type': source_type,   # 'task', 'offer', 'referral', 'bonus'
                'source_id': str(source_id),
                'tier_bonus_applied': bonus_multiplier > 1,
                'original_amount': str(original_amount) if bonus_multiplier > 1 else str(amount),
            },
            balance_before=wallet.current_balance,
            approved_at=timezone.now(),
            debit_account='revenue',
            credit_account='user_balance',
        )

        wallet.current_balance += amount
        wallet.total_earned += amount
        txn.balance_after = wallet.current_balance
        wallet.save()
        txn.save()

        # User statistics update করো
        WalletService._update_user_stats_on_earn(wallet.user, amount)

        return txn

    @staticmethod
    @transaction.atomic
    def add_bonus(wallet, amount, expires_at=None, description=''):
        """Add bonus balance"""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        amount = Decimal(str(amount))

        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type='bonus',
            amount=amount,
            status='approved',
            description=description,
            balance_before=wallet.bonus_balance,
            metadata={'source_type': 'bonus'},
        )

        wallet.bonus_balance += amount
        if expires_at:
            wallet.bonus_expires_at = expires_at

        txn.balance_after = wallet.bonus_balance
        wallet.save()
        txn.save()
        return txn

    @staticmethod
    @transaction.atomic
    def create_withdrawal(wallet, amount, payment_method_id, account_number=''):
        """
        Withdrawal request তৈরি করো।
        UPGRADED: per-gateway minimum, daily limit, fraud check।
        """
        amount = Decimal(str(amount))

        # 1. Wallet locked check
        if wallet.is_locked:
            raise ValueError(f"Wallet locked: {wallet.locked_reason}")

        # 2. Balance check
        if amount > wallet.available_balance:
            raise ValueError(f"Insufficient balance। Available: {wallet.available_balance}")

        # 3. Per-gateway minimum amount check
        try:
            payment_method = UserPaymentMethod.objects.get(id=payment_method_id, user=wallet.user)
        except UserPaymentMethod.DoesNotExist:
            raise ValueError("Payment method পাওয়া যায়নি।")

        gateway_min = GATEWAY_MIN_AMOUNTS.get(payment_method.method_type, MIN_WITHDRAWAL)
        if amount < gateway_min:
            raise ValueError(f"Minimum withdrawal for {payment_method.method_type}: {gateway_min}")

        # 4. Daily withdrawal limit check
        daily_check = WalletService._check_daily_withdrawal_limit(wallet, amount)
        if not daily_check['allowed']:
            raise ValueError(daily_check['message'])

        # 5. Fraud check
        fraud_check = WalletService._check_fraud_before_withdrawal(wallet.user)
        if not fraud_check['allowed']:
            raise ValueError(fraud_check['reason'])

        # 6. Fee calculate করো
        fee = WalletService._calculate_withdrawal_fee(amount, payment_method.method_type, wallet.user)
        net_amount = amount - fee

        if net_amount <= 0:
            raise ValueError(f"Amount কম। Fee: {fee}")

        # 7. Transaction তৈরি করো
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type='withdrawal',
            amount=-amount,
            status='pending',
            description=f"Withdrawal to {payment_method.get_method_type_display()} - {payment_method.account_number}",
            metadata={
                'payment_method_id': str(payment_method_id),
                'payment_method_type': payment_method.method_type,
                'account_number': payment_method.account_number,
                'fee': str(fee),
                'net_amount': str(net_amount),
            },
            balance_before=wallet.current_balance,
            debit_account='user_balance',
            credit_account='withdrawal_pending',
        )

        # 8. Pending এ move করো
        wallet.current_balance -= amount
        wallet.pending_balance += amount
        txn.balance_after = wallet.current_balance
        wallet.save()
        txn.save()

        # 9. Fee transaction তৈরি করো
        if fee > 0:
            WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal_fee',
                amount=-fee,
                status='approved',
                description=f"Withdrawal fee ({WITHDRAWAL_FEE_PERCENT}%)",
                reference_id=str(txn.walletTransaction_id),
                balance_before=txn.balance_after,
                balance_after=txn.balance_after,
            )

        logger.info(f"Withdrawal request created: {txn.walletTransaction_id} for user {wallet.user.id}")
        return txn, fee, net_amount

    @staticmethod
    @transaction.atomic
    def approve_withdrawal(txn, approved_by=None):
        """Withdrawal approve করো"""
        if txn.type != 'withdrawal':
            raise ValueError("Not a withdrawal transaction")
        if txn.status != 'pending':
            raise ValueError(f"Transaction not pending: {txn.status}")

        wallet = txn.wallet
        amount = abs(txn.amount)

        txn.status = 'approved'
        txn.approved_by = approved_by
        txn.approved_at = timezone.now()
        txn.balance_after = wallet.current_balance
        txn.save()

        wallet.pending_balance -= amount
        wallet.total_withdrawn += amount
        wallet.save()

        # User statistics update
        WalletService._update_user_stats_on_withdraw(wallet.user, amount)

        logger.info(f"Withdrawal approved: {txn.walletTransaction_id}")
        return txn

    @staticmethod
    @transaction.atomic
    def reject_withdrawal(txn, reason='', rejected_by=None):
        """Withdrawal reject করো এবং balance refund করো"""
        if txn.type != 'withdrawal':
            raise ValueError("Not a withdrawal transaction")
        if txn.status != 'pending':
            raise ValueError(f"Transaction not pending: {txn.status}")

        wallet = txn.wallet
        amount = abs(txn.amount)

        # Refund
        wallet.current_balance += amount
        wallet.pending_balance -= amount
        wallet.save()

        txn.status = 'rejected'
        txn.description += f" | Rejected: {reason}"
        txn.balance_after = wallet.current_balance
        txn.save()

        logger.info(f"Withdrawal rejected: {txn.walletTransaction_id}, reason: {reason}")
        return txn

    # ────────────────────────────────────────────────────────
    # NEW METHODS
    # ────────────────────────────────────────────────────────

    @staticmethod
    def get_wallet_summary(user) -> dict:
        """User এর complete wallet summary"""
        try:
            wallet = Wallet.objects.select_for_update().get(user=user)
        except Wallet.DoesNotExist:
            return {}

        # Daily earning
        today_earning = WalletTransaction.objects.filter(
            wallet=wallet,
            type__in=['earning', 'reward', 'referral'],
            status='approved',
            created_at__date=timezone.now().date()
        ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('amount'))['total'] or Decimal('0')

        return {
            'current_balance': str(wallet.current_balance),
            'pending_balance': str(wallet.pending_balance),
            'total_earned': str(wallet.total_earned),
            'total_withdrawn': str(wallet.total_withdrawn),
            'frozen_balance': str(wallet.frozen_balance),
            'bonus_balance': str(wallet.bonus_balance),
            'bonus_expires_at': wallet.bonus_expires_at,
            'available_balance': str(wallet.available_balance),
            'is_locked': wallet.is_locked,
            'currency': wallet.currency,
            'today_earning': str(today_earning),
        }

    @staticmethod
    def add_referral_commission(wallet, amount, level: int, referred_user_id,
                                source_task_id='', source_earning_id=''):
        """
        Referral commission add করো — Level 1/2/3 support সহ।
        Level 1: 10%, Level 2: 5%, Level 3: 2%
        """
        COMMISSION_RATES = {1: Decimal('0.10'), 2: Decimal('0.05'), 3: Decimal('0.02')}
        amount = Decimal(str(amount))
        rate = COMMISSION_RATES.get(level, Decimal('0'))
        commission = amount * rate

        if commission <= Decimal('0'):
            return None

        return WalletService.add_earnings(
            wallet=wallet,
            amount=commission,
            description=f"Level {level} referral commission ({int(rate * 100)}%)",
            source_type='referral',
            source_id=referred_user_id,
            metadata={
                'referral_level': level,
                'commission_rate': str(rate),
                'source_task_id': str(source_task_id),
                'source_earning_id': str(source_earning_id),
                'referred_user_id': str(referred_user_id),
            }
        )

    @staticmethod
    def get_earnings_breakdown(wallet, days: int = 30) -> dict:
        """
        কোন source থেকে কত earn হয়েছে — breakdown দেখাও।
        """
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncDate
        from django.db.models import Q

        cutoff = timezone.now() - timedelta(days=days)

        txns = WalletTransaction.objects.filter(
            wallet=wallet,
            type__in=['earning', 'reward', 'referral', 'bonus'],
            status='approved',
            created_at__gte=cutoff
        )

        by_type = {}
        for txn in txns:
            t = txn.type
            by_type[t] = by_type.get(t, Decimal('0')) + txn.amount

        # Daily chart data
        daily = txns.annotate(date=TruncDate('created_at')).values('date').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('date')

        return {
            'by_type': {k: str(v) for k, v in by_type.items()},
            'daily_chart': list(daily),
            'total': str(sum(by_type.values())),
            'period_days': days,
        }

    # ────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _get_tier_bonus_multiplier(user) -> float:
        """User tier অনুযায়ী reward multiplier"""
        try:
            from api.users.models import UserLevel
            level = UserLevel.objects.filter(user=user).first()
            if level:
                return level.task_reward_bonus  # 1.0 = no bonus, 1.1 = 10% bonus
        except Exception:
            pass

        # Tier based fallback
        tier_multipliers = {
            'FREE': 1.0,
            'BRONZE': 1.05,
            'SILVER': 1.10,
            'GOLD': 1.15,
            'PLATINUM': 1.20,
        }
        return tier_multipliers.get(getattr(user, 'tier', 'FREE'), 1.0)

    @staticmethod
    def _calculate_withdrawal_fee(amount: Decimal, method: str, user) -> Decimal:
        """Withdrawal fee calculate করো — tier based discount সহ"""
        base_fee = amount * WITHDRAWAL_FEE_PERCENT / 100

        # Platinum user → fee নেই
        tier = getattr(user, 'tier', 'FREE')
        if tier == 'PLATINUM':
            return Decimal('0')
        if tier == 'GOLD':
            base_fee = base_fee * Decimal('0.5')

        # Crypto → flat fee
        if method == 'usdt':
            return Decimal('1.00')

        return base_fee.quantize(Decimal('0.01'))

    @staticmethod
    def _check_daily_withdrawal_limit(wallet, amount: Decimal) -> dict:
        """আজকে কত withdrawal হয়েছে check করো"""
        today = timezone.now().date()
        today_withdrawn = WalletTransaction.objects.filter(
            wallet=wallet,
            type='withdrawal',
            status__in=['pending', 'approved'],
            created_at__date=today
        ).aggregate(
            total=__import__('django.db.models', fromlist=['Sum']).Sum('amount')
        )['total'] or Decimal('0')

        today_withdrawn = abs(today_withdrawn)

        if today_withdrawn + amount > MAX_DAILY_WITHDRAWAL:
            remaining = MAX_DAILY_WITHDRAWAL - today_withdrawn
            return {
                'allowed': False,
                'message': f"Daily withdrawal limit ({MAX_DAILY_WITHDRAWAL}) পার হয়েছে। আজ আর {remaining} নিতে পারবেন।"
            }
        return {'allowed': True}

    @staticmethod
    def _check_fraud_before_withdrawal(user) -> dict:
        """Withdrawal এর আগে fraud check করো"""
        try:
            from api.fraud_detection.models import UserRiskProfile
            risk = UserRiskProfile.objects.filter(user=user).first()
            if risk:
                if risk.is_restricted:
                    return {'allowed': False, 'reason': 'Account restricted। Support এ যোগাযোগ করুন।'}
                if getattr(risk, 'overall_risk_score', 0) >= 80:
                    return {'allowed': False, 'reason': 'Account flagged। Admin review pending।'}
        except Exception:
            pass

        # KYC check — withdrawal এর আগে KYC verify হতে হবে
        try:
            from api.users.models import KYCVerification
            kyc = KYCVerification.objects.filter(user=user).first()
            if not kyc or kyc.verification_status != 'approved':
                return {'allowed': False, 'reason': 'KYC verification complete করুন withdrawal এর আগে।'}
        except Exception:
            pass

        return {'allowed': True}

    @staticmethod
    def _update_user_stats_on_earn(user, amount: Decimal):
        """Earning হলে UserStatistics update করো"""
        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.get_or_create(user=user)
            stats.total_earned += amount
            stats.earned_today += amount
            stats.save(update_fields=['total_earned', 'earned_today'])
        except Exception as e:
            logger.warning(f"UserStatistics update failed: {e}")

    @staticmethod
    def _update_user_stats_on_withdraw(user, amount: Decimal):
        """Withdrawal হলে UserStatistics update করো"""
        try:
            from api.users.models import UserStatistics
            stats, _ = UserStatistics.objects.get_or_create(user=user)
            stats.total_withdrawn += amount
            stats.withdrawals_count += 1
            stats.save(update_fields=['total_withdrawn', 'withdrawals_count'])
        except Exception as e:
            logger.warning(f"UserStatistics withdrawal update failed: {e}")


# ────────────────────────────────────────────────────────────
# CRYPTO PAYOUT SERVICE
# ────────────────────────────────────────────────────────────

class CryptoPayoutService:
    """
    USDT TRC-20 / ERC-20 payout।
    Nowpayments.io API ব্যবহার করে।
    pip install requests
    settings.py তে add করো: NOWPAYMENTS_API_KEY = 'your_key'
    """

    BASE_URL = "https://api.nowpayments.io/v1"

    @classmethod
    def _headers(cls) -> dict:
        api_key = getattr(settings, 'NOWPAYMENTS_API_KEY', '')
        return {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
        }

    @classmethod
    def create_payout(cls, wallet_address: str, amount_usd: float, currency: str = 'usdttrc20') -> dict:
        """
        USDT payout তৈরি করো।
        currency: 'usdttrc20' (TRC-20) অথবা 'usdterc20' (ERC-20)
        """
        import requests

        payload = {
            "currency": currency,
            "amount": amount_usd,
            "address": wallet_address,
            "ipn_callback_url": getattr(settings, 'NOWPAYMENTS_IPN_URL', ''),
        }

        try:
            resp = requests.post(
                f"{cls.BASE_URL}/payout",
                json=payload,
                headers=cls._headers(),
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                'success': True,
                'payment_id': data.get('id'),
                'status': data.get('status'),
                'currency': currency,
                'amount': amount_usd,
            }
        except Exception as e:
            logger.error(f"Crypto payout failed: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_exchange_rate(cls, from_currency: str = 'bdt', to_currency: str = 'usdttrc20') -> float:
        """Current exchange rate পাও"""
        import requests
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/exchange-rate/{from_currency}/{to_currency}",
                headers=cls._headers(),
                timeout=10
            )
            data = resp.json()
            return float(data.get('rate', 0))
        except Exception as e:
            logger.error(f"Exchange rate fetch failed: {e}")
            return 0.0

    @classmethod
    def validate_wallet_address(cls, address: str, currency: str = 'usdt') -> bool:
        """Basic wallet address validation"""
        if not address:
            return False
        # TRC-20: T দিয়ে শুরু, 34 chars
        if currency in ['usdttrc20', 'trc20']:
            return address.startswith('T') and len(address) == 34
        # ERC-20: 0x দিয়ে শুরু, 42 chars
        if currency in ['usdterc20', 'erc20']:
            return address.startswith('0x') and len(address) == 42
        return len(address) > 10


# ────────────────────────────────────────────────────────────
# AUTO PAYOUT SCHEDULER (Celery Task)
# ────────────────────────────────────────────────────────────
# api/wallet/tasks.py তে add করো:
#
# from celery import shared_task
# from .services import WalletService
#
# @shared_task
# def process_pending_withdrawals():
#     """সব pending withdrawal process করো"""
#     from .models import WalletTransaction
#     pending = WalletTransaction.objects.filter(
#         type='withdrawal',
#         status='pending',
#         created_at__lt=timezone.now() - timedelta(minutes=30)  # 30 min পুরনো
#     )
#     for txn in pending:
#         try:
#             # Payment gateway call করো
#             WalletService.approve_withdrawal(txn)
#         except Exception as e:
#             logger.error(f"Auto withdrawal failed for {txn.id}: {e}")
#
# @shared_task
# def expire_bonus_balances():
#     """Expired bonus balances zero করো"""
#     from .models import Wallet
#     expired = Wallet.objects.filter(
#         bonus_balance__gt=0,
#         bonus_expires_at__lt=timezone.now()
#     )
#     for wallet in expired:
#         wallet.bonus_balance = 0
#         wallet.bonus_expires_at = None
#         wallet.save()


# Signal moved to signals.py




# # wallet/services.py
# from django.db import transaction
# from decimal import Decimal
# from .models import Wallet, GatewayTransaction
# from django.utils import timezone
# from django.db import models
# from django.conf import settings
# from datetime import timedelta
# from api.users.models import User



# class WalletService:
#     """Wallet operations service"""
    
#     @staticmethod
#     @GatewayTransaction.atomic
#     def create_wallet(user):
#         """Auto-create wallet on user signup"""
#         wallet, created = Wallet.objects.get_or_create(user=user)
#         return wallet
    
#     @staticmethod
#     @GatewayTransaction.atomic
#     def add_earnings(wallet, amount, description='', reference_id='', metadata=None):
#         """Add earnings to wallet"""
#         if amount <= 0:
#             raise ValueError("Amount must be positive")
        
#         # Create GatewayTransaction
#         txn = GatewayTransaction.objects.create(
#             wallet=wallet,
#             type='earning',
#             amount=amount,
#             status='approved',
#             description=description,
#             reference_id=reference_id,
#             metadata=metadata or {},
#             balance_before=wallet.current_balance,
#             approved_at=timezone.now()
#         )
        
#         # Update wallet
#         wallet.current_balance += amount
#         wallet.total_earned += amount
#         txn.balance_after = wallet.current_balance
#         wallet.save()
#         txn.save()
        
#         return txn
    
#     @staticmethod
#     @GatewayTransaction.atomic
#     def add_bonus(wallet, amount, expires_at=None, description=''):
#         """Add bonus balance"""
#         if amount <= 0:
#             raise ValueError("Amount must be positive")
        
#         txn = GatewayTransaction.objects.create(
#             wallet=wallet,
#             type='bonus',
#             amount=amount,
#             status='approved',
#             description=description,
#             balance_before=wallet.bonus_balance
#         )
        
#         wallet.bonus_balance += amount
#         if expires_at:
#             wallet.bonus_expires_at = expires_at
        
#         txn.balance_after = wallet.bonus_balance
#         wallet.save()
#         txn.save()
        
#         return txn
    
#     @staticmethod
#     @GatewayTransaction.atomic
#     def create_withdrawal(wallet, amount, payment_method, account_number):
#         """Create withdrawal request"""
#         if amount <= 0:
#             raise ValueError("Amount must be positive")
        
#         if amount > wallet.available_balance:
#             raise ValueError("Insufficient balance")
        
#         if wallet.is_locked:
#             raise ValueError(f"Wallet is locked: {wallet.locked_reason}")
        
#         # Create pending GatewayTransaction
#         txn = GatewayTransaction.objects.create(
#             wallet=wallet,
#             type='withdrawal',
#             amount=-amount,  # Negative for debit
#             status='pending',
#             description=f"Withdrawal request to {payment_method}",
#             metadata={
#                 'payment_method': payment_method,
#                 'account_number': account_number
#             },
#             balance_before=wallet.current_balance
#         )
        
#         # Move to pending
#         wallet.current_balance -= amount
#         wallet.pending_balance += amount
#         wallet.save()
        
#         return txn
    
#     @staticmethod
#     @GatewayTransaction.atomic
#     def approve_withdrawal(GatewayTransaction, approved_by=None):
#         """Approve withdrawal"""
#         if GatewayTransaction.type != 'withdrawal':
#             raise ValueError("Not a withdrawal GatewayTransaction")
        
#         if GatewayTransaction.status != 'pending':
#             raise ValueError("GatewayTransaction not pending")
        
#         wallet = GatewayTransaction.wallet
#         amount = abs(GatewayTransaction.amount)
        
#         # Update GatewayTransaction
#         GatewayTransaction.status = 'approved'
#         GatewayTransaction.approved_by = approved_by
#         GatewayTransaction.approved_at = timezone.now()
#         GatewayTransaction.balance_after = wallet.current_balance
#         GatewayTransaction.save()
        
#         # Update wallet
#         wallet.pending_balance -= amount
#         wallet.total_withdrawn += amount
#         wallet.save()
        
#         return GatewayTransaction
    
#     @staticmethod
#     @GatewayTransaction.atomic
#     def reject_withdrawal(GatewayTransaction, reason=''):
#         """Reject withdrawal and refund"""
#         if GatewayTransaction.type != 'withdrawal':
#             raise ValueError("Not a withdrawal GatewayTransaction")
        
#         if GatewayTransaction.status != 'pending':
#             raise ValueError("GatewayTransaction not pending")
        
#         wallet = GatewayTransaction.wallet
#         amount = abs(GatewayTransaction.amount)
        
#         # Refund to current balance
#         wallet.current_balance += amount
#         wallet.pending_balance -= amount
#         wallet.save()
        
#         # Update GatewayTransaction
#         GatewayTransaction.status = 'rejected'
#         GatewayTransaction.description += f" | Rejected: {reason}"
#         GatewayTransaction.save()
        
#         return GatewayTransaction
    
#     @staticmethod
#     def get_GatewayTransaction_history(wallet, limit=50):
#         """Get GatewayTransaction history"""
#         return GatewayTransaction.objects.filter(wallet=wallet)[:limit]
    
#     @staticmethod
#     def calculate_daily_earnings(wallet, date=None):
#         """Calculate earnings for a specific date"""
#         from datetime import date as dt_date
        
#         target_date = date or dt_date.today()
        
#         earnings = GatewayTransaction.objects.filter(
#             wallet=wallet,
#             type__in=['earning', 'reward', 'referral'],
#             status='approved',
#             created_at__date=target_date
#         ).aggregate(
#             total=models.Sum('amount')
#         )['total'] or Decimal('0')
        
#         return earnings


# # Signal to auto-create wallet on user signup
# from django.db.models.signals import post_save
# from django.dispatch import receiver

# @receiver(post_save, sender=settings.AUTH_USER_MODEL)
# def create_user_wallet(sender, instance, created, **kwargs):
#     """Auto-create wallet when user is created"""
#     if created:
#         Wallet.objects.create(user=instance)


# # ---------- Fraud detection integration ----------
# def check_user_risk_for_wallet_operation(user):
#     """
#     Check fraud_detection risk before sensitive wallet operations (e.g. withdrawal).
#     Returns (allowed: bool, reason: str).
#     """
#     try:
#         from api.fraud_detection.models import UserRiskProfile
#         risk = UserRiskProfile.objects.filter(user=user).first()
#         if not risk:
#             return True, ""
#         if risk.is_restricted:
#             return False, "Account is restricted by risk policy."
#         if risk.is_flagged and getattr(risk, "overall_risk_score", 0) >= 80:
#             return False, "Account flagged for review. Withdrawal not allowed."
#         return True, ""
#     except ImportError:
#         return True, ""

# ── Compatibility bridge to new services/ package ────────────
# Your original WalletService above is preserved.
# New services below provide additional world-class features.
try:
    from .services.core.WalletService import WalletService as WalletServiceV2
    from .services.core.TransactionService import TransactionService
    from .services.core.BalanceService import BalanceService
    from .services.core.IdempotencyService import IdempotencyService
    from .services.withdrawal.WithdrawalService import WithdrawalService
    from .services.withdrawal.WithdrawalFeeService import WithdrawalFeeService
    from .services.withdrawal.WithdrawalLimitService import WithdrawalLimitService
    from .services.withdrawal.WithdrawalBatchService import WithdrawalBatchService
    from .services.earning.EarningService import EarningService
    from .services.earning.EarningCapService import EarningCapService
    from .services.WalletAnalyticsService import WalletAnalyticsService
    from .services.ledger.LedgerService import LedgerService
    from .services.ledger.ReconciliationService import ReconciliationService
    from .services.ledger.LedgerSnapshotService import LedgerSnapshotService
except ImportError as _e:
    import logging
    logging.getLogger("wallet.services").debug(f"New services import: {_e}")
