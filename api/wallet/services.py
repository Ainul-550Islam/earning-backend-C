# wallet/services.py
from django.db import GatewayTransaction
from decimal import Decimal
from .models import Wallet, GatewayTransaction
from django.utils import timezone
from django.db import models
from django.conf import settings
from datetime import timedelta
from api.users.models import User



class WalletService:
    """Wallet operations service"""
    
    @staticmethod
    @GatewayTransaction.atomic
    def create_wallet(user):
        """Auto-create wallet on user signup"""
        wallet, created = Wallet.objects.get_or_create(user=user)
        return wallet
    
    @staticmethod
    @GatewayTransaction.atomic
    def add_earnings(wallet, amount, description='', reference_id='', metadata=None):
        """Add earnings to wallet"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Create GatewayTransaction
        txn = GatewayTransaction.objects.create(
            wallet=wallet,
            type='earning',
            amount=amount,
            status='approved',
            description=description,
            reference_id=reference_id,
            metadata=metadata or {},
            balance_before=wallet.current_balance,
            approved_at=timezone.now()
        )
        
        # Update wallet
        wallet.current_balance += amount
        wallet.total_earned += amount
        txn.balance_after = wallet.current_balance
        wallet.save()
        txn.save()
        
        return txn
    
    @staticmethod
    @GatewayTransaction.atomic
    def add_bonus(wallet, amount, expires_at=None, description=''):
        """Add bonus balance"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        txn = GatewayTransaction.objects.create(
            wallet=wallet,
            type='bonus',
            amount=amount,
            status='approved',
            description=description,
            balance_before=wallet.bonus_balance
        )
        
        wallet.bonus_balance += amount
        if expires_at:
            wallet.bonus_expires_at = expires_at
        
        txn.balance_after = wallet.bonus_balance
        wallet.save()
        txn.save()
        
        return txn
    
    @staticmethod
    @GatewayTransaction.atomic
    def create_withdrawal(wallet, amount, payment_method, account_number):
        """Create withdrawal request"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if amount > wallet.available_balance:
            raise ValueError("Insufficient balance")
        
        if wallet.is_locked:
            raise ValueError(f"Wallet is locked: {wallet.locked_reason}")
        
        # Create pending GatewayTransaction
        txn = GatewayTransaction.objects.create(
            wallet=wallet,
            type='withdrawal',
            amount=-amount,  # Negative for debit
            status='pending',
            description=f"Withdrawal request to {payment_method}",
            metadata={
                'payment_method': payment_method,
                'account_number': account_number
            },
            balance_before=wallet.current_balance
        )
        
        # Move to pending
        wallet.current_balance -= amount
        wallet.pending_balance += amount
        wallet.save()
        
        return txn
    
    @staticmethod
    @GatewayTransaction.atomic
    def approve_withdrawal(GatewayTransaction, approved_by=None):
        """Approve withdrawal"""
        if GatewayTransaction.type != 'withdrawal':
            raise ValueError("Not a withdrawal GatewayTransaction")
        
        if GatewayTransaction.status != 'pending':
            raise ValueError("GatewayTransaction not pending")
        
        wallet = GatewayTransaction.wallet
        amount = abs(GatewayTransaction.amount)
        
        # Update GatewayTransaction
        GatewayTransaction.status = 'approved'
        GatewayTransaction.approved_by = approved_by
        GatewayTransaction.approved_at = timezone.now()
        GatewayTransaction.balance_after = wallet.current_balance
        GatewayTransaction.save()
        
        # Update wallet
        wallet.pending_balance -= amount
        wallet.total_withdrawn += amount
        wallet.save()
        
        return GatewayTransaction
    
    @staticmethod
    @GatewayTransaction.atomic
    def reject_withdrawal(GatewayTransaction, reason=''):
        """Reject withdrawal and refund"""
        if GatewayTransaction.type != 'withdrawal':
            raise ValueError("Not a withdrawal GatewayTransaction")
        
        if GatewayTransaction.status != 'pending':
            raise ValueError("GatewayTransaction not pending")
        
        wallet = GatewayTransaction.wallet
        amount = abs(GatewayTransaction.amount)
        
        # Refund to current balance
        wallet.current_balance += amount
        wallet.pending_balance -= amount
        wallet.save()
        
        # Update GatewayTransaction
        GatewayTransaction.status = 'rejected'
        GatewayTransaction.description += f" | Rejected: {reason}"
        GatewayTransaction.save()
        
        return GatewayTransaction
    
    @staticmethod
    def get_GatewayTransaction_history(wallet, limit=50):
        """Get GatewayTransaction history"""
        return GatewayTransaction.objects.filter(wallet=wallet)[:limit]
    
    @staticmethod
    def calculate_daily_earnings(wallet, date=None):
        """Calculate earnings for a specific date"""
        from datetime import date as dt_date
        
        target_date = date or dt_date.today()
        
        earnings = GatewayTransaction.objects.filter(
            wallet=wallet,
            type__in=['earning', 'reward', 'referral'],
            status='approved',
            created_at__date=target_date
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        return earnings


# Signal to auto-create wallet on user signup
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_wallet(sender, instance, created, **kwargs):
    """Auto-create wallet when user is created"""
    if created:
        Wallet.objects.create(user=instance)


# ---------- Fraud detection integration ----------
def check_user_risk_for_wallet_operation(user):
    """
    Check fraud_detection risk before sensitive wallet operations (e.g. withdrawal).
    Returns (allowed: bool, reason: str).
    """
    try:
        from api.fraud_detection.models import UserRiskProfile
        risk = UserRiskProfile.objects.filter(user=user).first()
        if not risk:
            return True, ""
        if risk.is_restricted:
            return False, "Account is restricted by risk policy."
        if risk.is_flagged and getattr(risk, "overall_risk_score", 0) >= 80:
            return False, "Account flagged for review. Withdrawal not allowed."
        return True, ""
    except ImportError:
        return True, ""