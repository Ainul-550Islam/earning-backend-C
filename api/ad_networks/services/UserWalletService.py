"""
api/ad_networks/services/UserWalletService.py
Service for managing user wallets and transactions
SaaS-ready with tenant support
"""

from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from ..models import UserWallet, OfferReward
from ..constants import WALLET_TRANSACTION_TYPES
from .base import BaseService

User = get_user_model()


class UserWalletService(BaseService):
    """Service for managing user wallets and transactions"""
    
    def __init__(self, tenant_id=None):
        super().__init__(tenant_id)
    
    def get_or_create_wallet(self, user_id, currency='BDT'):
        """Get or create user wallet"""
        try:
            wallet, created = UserWallet.objects.get_or_create(
                user_id=user_id,
                tenant_id=self.tenant_id,
                defaults={
                    'currency': currency,
                    'current_balance': Decimal('0.00'),
                    'total_earned': Decimal('0.00'),
                    'total_withdrawn': Decimal('0.00'),
                    'pending_balance': Decimal('0.00'),
                    'daily_limit': Decimal('5000.00'),
                    'monthly_limit': Decimal('100000.00'),
                    'is_active': True,
                    'is_frozen': False
                }
            )
            
            if created:
                self.logger.info(f"Created new wallet for user {user_id}")
            
            return wallet
            
        except Exception as e:
            self.logger.error(f"Error getting/creating wallet: {str(e)}")
            raise
    
    def get_wallet_balance(self, user_id):
        """Get current wallet balance"""
        try:
            wallet = UserWallet.objects.get(
                user_id=user_id,
                tenant_id=self.tenant_id
            )
            return {
                'current_balance': wallet.current_balance,
                'available_balance': wallet.available_balance,
                'pending_balance': wallet.pending_balance,
                'total_earned': wallet.total_earned,
                'total_withdrawn': wallet.total_withdrawn,
                'currency': wallet.currency
            }
        except UserWallet.DoesNotExist:
            return None
    
    def credit_wallet(self, user_id, amount, description=None, reference_id=None):
        """Credit amount to user wallet"""
        try:
            with transaction.atomic():
                wallet = self.get_or_create_wallet(user_id)
                
                # Validate amount
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                
                # Update wallet
                wallet.current_balance += amount
                wallet.total_earned += amount
                wallet.save(update_fields=['current_balance', 'total_earned'])
                
                # Create transaction record (if transaction model exists)
                self._create_transaction(
                    wallet=wallet,
                    transaction_type='credit',
                    amount=amount,
                    description=description or 'Wallet credit',
                    reference_id=reference_id
                )
                
                self.logger.info(f"Credited {amount} to wallet {wallet.id}")
                return wallet
                
        except Exception as e:
            self.logger.error(f"Error crediting wallet: {str(e)}")
            raise
    
    def debit_wallet(self, user_id, amount, description=None, reference_id=None):
        """Debit amount from user wallet"""
        try:
            with transaction.atomic():
                wallet = UserWallet.objects.get(
                    user_id=user_id,
                    tenant_id=self.tenant_id
                )
                
                # Validate amount
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                
                # Check sufficient balance
                if wallet.available_balance < amount:
                    raise ValueError("Insufficient balance")
                
                # Check if wallet is frozen
                if wallet.is_frozen:
                    raise ValueError("Wallet is frozen")
                
                # Check if wallet is active
                if not wallet.is_active:
                    raise ValueError("Wallet is inactive")
                
                # Update wallet
                wallet.current_balance -= amount
                wallet.total_withdrawn += amount
                wallet.save(update_fields=['current_balance', 'total_withdrawn'])
                
                # Create transaction record
                self._create_transaction(
                    wallet=wallet,
                    transaction_type='debit',
                    amount=amount,
                    description=description or 'Wallet debit',
                    reference_id=reference_id
                )
                
                self.logger.info(f"Debited {amount} from wallet {wallet.id}")
                return wallet
                
        except UserWallet.DoesNotExist:
            raise ValueError("Wallet not found")
        except Exception as e:
            self.logger.error(f"Error debiting wallet: {str(e)}")
            raise
    
    def add_pending_balance(self, user_id, amount, description=None, reference_id=None):
        """Add amount to pending balance"""
        try:
            with transaction.atomic():
                wallet = self.get_or_create_wallet(user_id)
                
                # Validate amount
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                
                # Update pending balance
                wallet.pending_balance += amount
                wallet.save(update_fields=['pending_balance'])
                
                # Create transaction record
                self._create_transaction(
                    wallet=wallet,
                    transaction_type='pending',
                    amount=amount,
                    description=description or 'Pending reward',
                    reference_id=reference_id
                )
                
                self.logger.info(f"Added {amount} to pending balance for wallet {wallet.id}")
                return wallet
                
        except Exception as e:
            self.logger.error(f"Error adding pending balance: {str(e)}")
            raise
    
    def confirm_pending_balance(self, user_id, amount, description=None, reference_id=None):
        """Confirm pending balance (move from pending to current)"""
        try:
            with transaction.atomic():
                wallet = UserWallet.objects.get(
                    user_id=user_id,
                    tenant_id=self.tenant_id
                )
                
                # Validate amount
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                
                # Check sufficient pending balance
                if wallet.pending_balance < amount:
                    raise ValueError("Insufficient pending balance")
                
                # Update wallet
                wallet.pending_balance -= amount
                wallet.current_balance += amount
                wallet.total_earned += amount
                wallet.save(update_fields=['pending_balance', 'current_balance', 'total_earned'])
                
                # Create transaction record
                self._create_transaction(
                    wallet=wallet,
                    transaction_type='confirm',
                    amount=amount,
                    description=description or 'Confirmed pending reward',
                    reference_id=reference_id
                )
                
                self.logger.info(f"Confirmed {amount} pending balance for wallet {wallet.id}")
                return wallet
                
        except UserWallet.DoesNotExist:
            raise ValueError("Wallet not found")
        except Exception as e:
            self.logger.error(f"Error confirming pending balance: {str(e)}")
            raise
    
    def cancel_pending_balance(self, user_id, amount, description=None, reference_id=None):
        """Cancel pending balance"""
        try:
            with transaction.atomic():
                wallet = UserWallet.objects.get(
                    user_id=user_id,
                    tenant_id=self.tenant_id
                )
                
                # Validate amount
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                
                # Check sufficient pending balance
                if wallet.pending_balance < amount:
                    raise ValueError("Insufficient pending balance")
                
                # Update wallet
                wallet.pending_balance -= amount
                wallet.save(update_fields=['pending_balance'])
                
                # Create transaction record
                self._create_transaction(
                    wallet=wallet,
                    transaction_type='cancel',
                    amount=amount,
                    description=description or 'Cancelled pending reward',
                    reference_id=reference_id
                )
                
                self.logger.info(f"Cancelled {amount} pending balance for wallet {wallet.id}")
                return wallet
                
        except UserWallet.DoesNotExist:
            raise ValueError("Wallet not found")
        except Exception as e:
            self.logger.error(f"Error cancelling pending balance: {str(e)}")
            raise
    
    def freeze_wallet(self, user_id, reason=None):
        """Freeze user wallet"""
        try:
            wallet = UserWallet.objects.get(
                user_id=user_id,
                tenant_id=self.tenant_id
            )
            
            wallet.is_frozen = True
            wallet.freeze_reason = reason
            wallet.frozen_at = timezone.now()
            wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
            
            self.logger.info(f"Frozen wallet {wallet.id} for user {user_id}")
            return wallet
            
        except UserWallet.DoesNotExist:
            raise ValueError("Wallet not found")
        except Exception as e:
            self.logger.error(f"Error freezing wallet: {str(e)}")
            raise
    
    def unfreeze_wallet(self, user_id):
        """Unfreeze user wallet"""
        try:
            wallet = UserWallet.objects.get(
                user_id=user_id,
                tenant_id=self.tenant_id
            )
            
            wallet.is_frozen = False
            wallet.freeze_reason = None
            wallet.frozen_at = None
            wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
            
            self.logger.info(f"Unfrozen wallet {wallet.id} for user {user_id}")
            return wallet
            
        except UserWallet.DoesNotExist:
            raise ValueError("Wallet not found")
        except Exception as e:
            self.logger.error(f"Error unfreezing wallet: {str(e)}")
            raise
    
    def update_wallet_limits(self, user_id, daily_limit=None, monthly_limit=None):
        """Update wallet limits"""
        try:
            wallet = UserWallet.objects.get(
                user_id=user_id,
                tenant_id=self.tenant_id
            )
            
            if daily_limit is not None:
                wallet.daily_limit = daily_limit
            
            if monthly_limit is not None:
                wallet.monthly_limit = monthly_limit
            
            wallet.save(update_fields=['daily_limit', 'monthly_limit'])
            
            self.logger.info(f"Updated limits for wallet {wallet.id}")
            return wallet
            
        except UserWallet.DoesNotExist:
            raise ValueError("Wallet not found")
        except Exception as e:
            self.logger.error(f"Error updating wallet limits: {str(e)}")
            raise
    
    def check_withdrawal_eligibility(self, user_id, amount):
        """Check if user can withdraw amount"""
        try:
            wallet = UserWallet.objects.get(
                user_id=user_id,
                tenant_id=self.tenant_id
            )
            
            # Check various conditions
            checks = {
                'sufficient_balance': wallet.available_balance >= amount,
                'wallet_active': wallet.is_active,
                'wallet_not_frozen': not wallet.is_frozen,
                'within_daily_limit': amount <= wallet.daily_limit,
                'within_monthly_limit': amount <= wallet.monthly_limit,
                'positive_amount': amount > 0
            }
            
            return all(checks.values()), checks
            
        except UserWallet.DoesNotExist:
            return False, {'wallet_exists': False}
        except Exception as e:
            self.logger.error(f"Error checking withdrawal eligibility: {str(e)}")
            return False, {'error': str(e)}
    
    def get_wallet_statistics(self, user_id):
        """Get wallet statistics for a user"""
        try:
            wallet = UserWallet.objects.get(
                user_id=user_id,
                tenant_id=self.tenant_id
            )
            
            # Calculate statistics
            stats = {
                'current_balance': float(wallet.current_balance),
                'available_balance': float(wallet.available_balance),
                'pending_balance': float(wallet.pending_balance),
                'total_earned': float(wallet.total_earned),
                'total_withdrawn': float(wallet.total_withdrawn),
                'currency': wallet.currency,
                'is_active': wallet.is_active,
                'is_frozen': wallet.is_frozen,
                'daily_limit': float(wallet.daily_limit),
                'monthly_limit': float(wallet.monthly_limit),
                'freeze_reason': wallet.freeze_reason,
                'frozen_at': wallet.frozen_at.isoformat() if wallet.frozen_at else None,
                'created_at': wallet.created_at.isoformat(),
                'updated_at': wallet.updated_at.isoformat()
            }
            
            return stats
            
        except UserWallet.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting wallet statistics: {str(e)}")
            raise
    
    def _create_transaction(self, wallet, transaction_type, amount, description, reference_id=None):
        """Create transaction record (placeholder for future transaction model)"""
        # This is a placeholder for when we implement a proper transaction model
        # For now, we'll just log the transaction
        self.logger.info(f"Transaction: {transaction_type} {amount} for wallet {wallet.id} - {description}")
        
        # In a full implementation, this would create a WalletTransaction record
        # WalletTransaction.objects.create(
        #     wallet=wallet,
        #     transaction_type=transaction_type,
        #     amount=amount,
        #     description=description,
        #     reference_id=reference_id,
        #     tenant_id=self.tenant_id
        # )
    
    def process_reward_payment(self, reward_id):
        """Process reward payment to user wallet"""
        try:
            with transaction.atomic():
                reward = OfferReward.objects.get(
                    id=reward_id,
                    tenant_id=self.tenant_id
                )
                
                if reward.status != 'approved':
                    raise ValueError("Reward must be approved before payment")
                
                # Add to pending balance first
                self.add_pending_balance(
                    user_id=reward.user.id,
                    amount=reward.amount,
                    description=f"Reward from {reward.offer.title}",
                    reference_id=f"reward_{reward.id}"
                )
                
                # Update reward status
                reward.status = 'paid'
                reward.paid_at = timezone.now()
                reward.save(update_fields=['status', 'paid_at'])
                
                self.logger.info(f"Processed payment for reward {reward_id}")
                return reward
                
        except OfferReward.DoesNotExist:
            raise ValueError("Reward not found")
        except Exception as e:
            self.logger.error(f"Error processing reward payment: {str(e)}")
            raise
