"""
Task Service Layer - Handles all business logic for task processing, revenue distribution,
and wallet management with bulletproof error handling.
"""

import logging
import decimal
from typing import Optional, Dict, Any, Tuple, List, Union
from decimal import Decimal
from datetime import timedelta  # [OK] Fixed: Added timedelta import
from django.db import transaction, models  # [OK] Fixed: Added models import
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
# tasks/services.py ফাইলে ইমপোর্টগুলো পরিবর্তন করুন
from users.models import Profile  # api/users/models.py থেকে
from wallet.models import WalletTransaction  # api/wallet/models.py থেকে

# Import models
from .models import MasterTask, UserTaskCompletion

# Get user model
User = get_user_model()

# Setup logging
logger = logging.getLogger(__name__)

# ============ CONSTANTS ============

class RevenueDistribution:
    """Constants for revenue distribution percentages"""
    
    USER_SHARE = Decimal('0.70')      # 70% to user
    REFERRAL_SHARE = Decimal('0.10')   # 10% to referrer
    ADMIN_SHARE = Decimal('0.20')       # 20% to admin profit
    
    # When no referrer, admin gets referral share too
    ADMIN_WITHOUT_REFERRAL = ADMIN_SHARE + REFERRAL_SHARE  # 30%


class TransactionStatus:
    """Transaction status constants"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class TransactionType:
    """Transaction type constants"""
    TASK_REWARD = 'task_reward'
    REFERRAL_BONUS = 'referral_bonus'
    ADMIN_PROFIT = 'admin_profit'
    WITHDRAWAL = 'withdrawal'
    DEPOSIT = 'deposit'


# ============ CONFIGURATION ============

class ServiceConfig:
    """Centralized configuration for services"""
    
    # Welcome bonus amount (from settings or default)
    WELCOME_BONUS = getattr(settings, 'REFERRAL_WELCOME_BONUS', Decimal('10'))
    
    # Minimum withdrawal amount
    MIN_WITHDRAWAL = getattr(settings, 'MIN_WITHDRAWAL_AMOUNT', Decimal('100'))
    
    # Cache timeouts (in seconds)
    CACHE_BALANCE_TIMEOUT = getattr(settings, 'CACHE_BALANCE_TIMEOUT', 300)
    CACHE_STATS_TIMEOUT = getattr(settings, 'CACHE_STATS_TIMEOUT', 3600)
    
    # Transaction limits
    MAX_TRANSACTION_HISTORY = getattr(settings, 'MAX_TRANSACTION_HISTORY', 50)


# ============ HELPER FUNCTIONS ============

def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """Safely convert to Decimal"""
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            return Decimal(value)
        return default
    except (TypeError, ValueError, decimal.InvalidOperation, ArithmeticError) as e:
        logger.warning(f"Failed to convert {value} to Decimal: {str(e)}, using default {default}")
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float"""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_profile_model():
    """Dynamically get the Profile model to avoid circular imports"""
    try:
        from .models import Profile
        return Profile
    except ImportError:
        logger.error("Profile model not found. Please create it in models.py")
        return None
    except Exception as e:
        logger.error(f"Error getting Profile model: {str(e)}")
        return None


def get_transaction_model():
    """Dynamically get the Transaction model to avoid circular imports"""
    try:
        from .models import Transaction
        return Transaction
    except ImportError:
        logger.error("Transaction model not found. Please create it in models.py")
        return None
    except Exception as e:
        logger.error(f"Error getting Transaction model: {str(e)}")
        return None


def get_admin_ledger_model():
    """Dynamically get the AdminLedger model to avoid circular imports"""
    try:
        from .models import AdminLedger
        return AdminLedger
    except ImportError:
        logger.error("AdminLedger model not found. Please create it in models.py")
        return None
    except Exception as e:
        logger.error(f"Error getting AdminLedger model: {str(e)}")
        return None


def get_user_profile(user) -> Optional[Any]:
    """
    Safely get user profile with multiple fallback methods
    Returns profile object or None
    """
    try:
        # Method 1: Direct profile relation
        if hasattr(user, 'profile'):
            return user.profile
        
        # Method 2: Try to get from related name
        if hasattr(user, 'user_profile'):
            return user.user_profile
        
        # Method 3: Try to get from OneToOne relation
        Profile = get_profile_model()
        if Profile:
            profile, created = Profile.objects.get_or_create(user=user)
            return profile
        
        logger.warning(f"No profile found for user {user.id} and could not create one")
        return None
        
    except Exception as e:
        logger.error(f"Error getting user profile for {getattr(user, 'id', 'unknown')}: {str(e)}")
        return None


def get_referrer(user) -> Optional[User]:
    """Get user's referrer safely"""
    try:
        profile = get_user_profile(user)
        if profile and hasattr(profile, 'referred_by'):
            referrer = profile.referred_by
            if referrer and isinstance(referrer, User):
                return referrer
        return None
    except Exception as e:
        logger.error(f"Error getting referrer for user {getattr(user, 'id', 'unknown')}: {str(e)}")
        return None


def update_user_balance(
    user: User, 
    amount: Decimal, 
    transaction_type: str, 
    metadata: Dict = None
) -> bool:
    """Update user balance with transaction logging"""
    try:
        with transaction.atomic():
            profile = get_user_profile(user)
            if not profile:
                logger.error(f"Cannot update balance: No profile for user {user.id}")
                return False
            
            # Determine which balance field to use
            balance_field = None
            if hasattr(profile, 'balance'):
                balance_field = 'balance'
            elif hasattr(profile, 'coins'):
                balance_field = 'coins'
            elif hasattr(profile, 'points'):
                balance_field = 'points'
            else:
                logger.error(f"Profile has no balance field for user {user.id}")
                return False
            
            # Update balance using F expression to avoid race conditions
            current_balance = getattr(profile, balance_field, Decimal('0'))
            new_balance = safe_decimal(current_balance) + amount
            
            setattr(profile, balance_field, new_balance)
            profile.save(update_fields=[balance_field])
            
            # Log transaction
            log_transaction(
                user=user,
                amount=amount,
                transaction_type=transaction_type,
                metadata=metadata
            )
            
            # Clear cache
            cache.delete(f"user_balance_{user.id}")
            
            logger.info(f"Updated balance for user {user.id}: +{amount} ({transaction_type})")
            return True
            
    except Exception as e:
        logger.error(f"Error updating user balance: {str(e)}", exc_info=True)
        return False


def log_transaction(
    user: User, 
    amount: Decimal, 
    transaction_type: str, 
    metadata: Dict = None
) -> bool:
    """Log transaction for auditing"""
    try:
        Transaction = get_transaction_model()
        if not Transaction:
            logger.warning("Transaction model not available, skipping log")
            return False
        
        Transaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=transaction_type,
            metadata=metadata or {},
            timestamp=timezone.now()
        )
        return True
        
    except Exception as e:
        logger.error(f"Error logging transaction: {str(e)}")
        return False


def update_admin_profit(
    amount: Decimal, 
    source: str, 
    metadata: Dict = None
) -> bool:
    """Update admin profit ledger"""
    try:
        AdminLedger = get_admin_ledger_model()
        if not AdminLedger:
            logger.warning("AdminLedger model not available, skipping profit update")
            return False
        
        AdminLedger.objects.create(
            amount=amount,
            source=source,
            metadata=metadata or {},
            timestamp=timezone.now()
        )
        
        # Update cache
        cache_key = "admin_total_profit"
        current = cache.get(cache_key, Decimal('0'))
        cache.set(cache_key, safe_decimal(current) + amount, timeout=ServiceConfig.CACHE_STATS_TIMEOUT)
        
        logger.info(f"Admin profit updated: +{amount} from {source}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating admin profit: {str(e)}")
        return False


# ============ REVENUE DISTRIBUTION SERVICE ============

class RevenueDistributionService:
    """
    Service class for handling revenue distribution logic
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @transaction.atomic
    def process_task_revenue(
        self, 
        user: User,
        task: MasterTask, 
        revenue_amount: Union[Decimal, float, int, str],
        completion: Optional[UserTaskCompletion] = None,
        metadata: Dict = None
    ) -> Dict[str, Any]:
        """
        Process revenue distribution for a completed task
        
        Args:
            user: The user who completed the task
            task: The task that was completed
            revenue_amount: Total revenue from this task (your earnings)
            completion: Optional completion object
            metadata: Additional metadata for tracking
        
        Returns:
            Dictionary with distribution details
        """
        try:
            # Convert to Decimal safely
            revenue = safe_decimal(revenue_amount)
            
            if revenue <= 0:
                return {
                    'success': False,
                    'error': f'Invalid revenue amount: {revenue}',
                    'distribution': None
                }
            
            self.logger.info(f"Processing revenue {revenue} for user {user.id}, task {task.task_id}")
            
            # Calculate shares
            user_share = revenue * RevenueDistribution.USER_SHARE
            referral_share = revenue * RevenueDistribution.REFERRAL_SHARE
            admin_share = revenue * RevenueDistribution.ADMIN_SHARE
            
            # Check for referrer
            referrer = get_referrer(user)
            referrer_user = None
            had_referrer = False
            
            if referrer:
                referrer_user = referrer
                had_referrer = True
                self.logger.info(f"User has referrer: {referrer.username}")
            else:
                self.logger.info("User has no referrer")
                # When no referrer, admin gets referral share too
                admin_share += referral_share
                referral_share = Decimal('0')
            
            # Update balances
            results = {
                'user': {'id': user.id, 'amount': float(user_share), 'success': False},
                'referrer': {'id': None, 'amount': 0, 'success': False},
                'admin': {'amount': float(admin_share), 'success': False}
            }
            
            # 1. Credit user
            user_success = update_user_balance(
                user=user,
                amount=user_share,
                transaction_type=TransactionType.TASK_REWARD,
                metadata={
                    'task_id': task.id,
                    'task_name': task.name,
                    'revenue': float(revenue),
                    'share_percentage': float(RevenueDistribution.USER_SHARE * 100),
                    'completion_id': completion.id if completion else None,
                    **(metadata or {})
                }
            )
            
            results['user']['success'] = user_success
            
            # 2. Credit referrer if exists
            if referrer_user and referral_share > 0:
                referrer_success = update_user_balance(
                    user=referrer_user,
                    amount=referral_share,
                    transaction_type=TransactionType.REFERRAL_BONUS,
                    metadata={
                        'referred_user_id': user.id,
                        'referred_username': user.username,
                        'task_id': task.id,
                        'task_name': task.name,
                        'revenue': float(revenue),
                        'share_percentage': float(RevenueDistribution.REFERRAL_SHARE * 100),
                        'completion_id': completion.id if completion else None
                    }
                )
                
                results['referrer'] = {
                    'id': referrer_user.id,
                    'username': referrer_user.username,
                    'amount': float(referral_share),
                    'success': referrer_success
                }
            
            # 3. Credit admin profit
            admin_success = update_admin_profit(
                amount=admin_share,
                source=f"task_{task.task_id}",
                metadata={
                    'user_id': user.id,
                    'username': user.username,
                    'task_id': task.id,
                    'task_name': task.name,
                    'revenue': float(revenue),
                    'had_referrer': had_referrer,
                    'completion_id': completion.id if completion else None
                }
            )
            
            results['admin']['success'] = admin_success
            results['admin']['had_referrer'] = had_referrer
            
            # Update completion if provided
            if completion:
                completion.rewards_awarded = {
                    'user_share': float(user_share),
                    'referral_share': float(referral_share) if referrer_user else 0,
                    'admin_share': float(admin_share),
                    'total_revenue': float(revenue),
                    'had_referrer': had_referrer,
                    'distribution_time': timezone.now().isoformat()
                }
                completion.save(update_fields=['rewards_awarded'])
            
            self.logger.info(f"Revenue distribution completed: {results}")
            
            return {
                'success': True,
                'distribution': results,
                'summary': {
                    'total_revenue': float(revenue),
                    'user_earned': float(user_share),
                    'referrer_earned': float(referral_share) if referrer_user else 0,
                    'admin_profit': float(admin_share),
                    'had_referrer': had_referrer
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error processing task revenue: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'distribution': None
            }


# ============ TASK VERIFICATION SERVICE ============

class TaskVerificationService:
    """
    Service for handling task verification and approval
    """
    
    def __init__(self):
        self.revenue_service = RevenueDistributionService()
        self.logger = logging.getLogger(__name__)
    
    @transaction.atomic
    def verify_and_distribute(
        self,
        completion: UserTaskCompletion,
        actual_revenue: Union[Decimal, float, int, str],
        verified_by: str = 'system',
        metadata: Dict = None
    ) -> Dict[str, Any]:
        """
        Verify a task completion and distribute revenue
        
        This should be called AFTER you confirm receiving payment
        """
        try:
            # Convert revenue to Decimal
            revenue = safe_decimal(actual_revenue)
            
            self.logger.info(f"Verifying completion {completion.id} with revenue {revenue}")
            
            # Check if already verified
            if getattr(completion, 'is_verified_by_admin', False):
                return {
                    'success': False,
                    'error': 'Task already verified',
                    'status': 'already_verified'
                }
            
            # Mark as verified
            completion.is_verified_by_admin = True
            completion.admin_revenue_received = revenue
            completion.verified_at = timezone.now()
            completion.status = 'completed'
            completion.save(update_fields=[
                'is_verified_by_admin', 
                'admin_revenue_received', 
                'verified_at',
                'status'
            ])
            
            # Process revenue distribution
            distribution_result = self.revenue_service.process_task_revenue(
                user=completion.user,
                task=completion.task,
                revenue_amount=revenue,
                completion=completion,
                metadata={
                    'verified_by': verified_by,
                    'verification_time': timezone.now().isoformat(),
                    **(metadata or {})
                }
            )
            
            if distribution_result.get('success', False):
                self.logger.info(f"Successfully verified and distributed for completion {completion.id}")
                
                # Clear relevant caches
                cache.delete(f'user_tasks_{completion.user.id}')
                cache.delete(f'task_stats_{completion.task.id}')
                
                return {
                    'success': True,
                    'completion_id': completion.id,
                    'distribution': distribution_result.get('distribution'),
                    'summary': distribution_result.get('summary')
                }
            else:
                # Distribution failed, but task is verified
                self.logger.error(f"Distribution failed after verification: {distribution_result.get('error')}")
                return {
                    'success': True,
                    'warning': 'Task verified but distribution failed',
                    'completion_id': completion.id,
                    'error': distribution_result.get('error')
                }
            
        except Exception as e:
            self.logger.error(f"Error in verify_and_distribute: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @transaction.atomic
    def batch_verify(
        self, 
        completion_ids: List[int], 
        revenue_per_task: Union[Decimal, float, int, str]
    ) -> Dict[str, Any]:
        """
        Batch verify multiple task completions
        """
        results = {
            'success': [],
            'failed': [],
            'total_processed': 0,
            'total_revenue': 0,
            'total_distributed': 0
        }
        
        try:
            revenue = safe_decimal(revenue_per_task)
            
            completions = UserTaskCompletion.objects.filter(
                id__in=completion_ids,
                is_verified_by_admin=False
            ).select_related('user', 'task')
            
            for completion in completions:
                try:
                    result = self.verify_and_distribute(
                        completion=completion,
                        actual_revenue=revenue,
                        verified_by='batch_system'
                    )
                    
                    if result.get('success', False):
                        results['success'].append({
                            'id': completion.id,
                            'user_id': completion.user.id,
                            'task': completion.task.task_id,
                            'summary': result.get('summary')
                        })
                        results['total_revenue'] += float(revenue)
                        if result.get('summary'):
                            results['total_distributed'] += result['summary'].get('user_earned', 0)
                    else:
                        results['failed'].append({
                            'id': completion.id,
                            'error': result.get('error', 'Unknown error')
                        })
                    
                    results['total_processed'] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error in batch verify for completion {completion.id}: {str(e)}")
                    results['failed'].append({
                        'id': completion.id,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in batch_verify: {str(e)}")
            return results


# ============ WALLET SERVICE ============

class WalletService:
    """
    Service for wallet operations and balance management
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_balance(self, user: User) -> Decimal:
        """Get user's current balance"""
        try:
            profile = get_user_profile(user)
            if not profile:
                return Decimal('0')
            
            # Try different balance fields
            if hasattr(profile, 'balance'):
                return safe_decimal(profile.balance)
            elif hasattr(profile, 'coins'):
                return safe_decimal(profile.coins)
            elif hasattr(profile, 'points'):
                return safe_decimal(profile.points)
            
            return Decimal('0')
            
        except Exception as e:
            self.logger.error(f"Error getting balance for user {getattr(user, 'id', 'unknown')}: {str(e)}")
            return Decimal('0')
    
    def get_balance_cached(self, user: User) -> Decimal:
        """Get user's balance with caching"""
        try:
            cache_key = f"user_balance_{user.id}"
            cached = cache.get(cache_key)
            
            if cached is not None:
                return Decimal(str(cached))
            
            balance = self.get_balance(user)
            cache.set(cache_key, float(balance), timeout=ServiceConfig.CACHE_BALANCE_TIMEOUT)
            return balance
            
        except Exception as e:
            self.logger.error(f"Error getting cached balance: {str(e)}")
            return self.get_balance(user)
    
    @transaction.atomic
    def add_funds(
        self, 
        user: User, 
        amount: Union[Decimal, float, int, str], 
        reason: str, 
        metadata: Dict = None
    ) -> bool:
        """Add funds to user wallet"""
        try:
            return update_user_balance(
                user=user,
                amount=safe_decimal(amount),
                transaction_type=TransactionType.DEPOSIT,
                metadata={
                    'reason': reason,
                    **(metadata or {})
                }
            )
        except Exception as e:
            self.logger.error(f"Error adding funds: {str(e)}")
            return False
    
    @transaction.atomic
    def withdraw_funds(
        self, 
        user: User, 
        amount: Union[Decimal, float, int, str], 
        payment_method: str, 
        metadata: Dict = None
    ) -> Dict[str, Any]:
        """Process withdrawal request"""
        try:
            withdraw_amount = safe_decimal(amount)
            current_balance = self.get_balance(user)
            
            # Check minimum withdrawal
            if withdraw_amount < ServiceConfig.MIN_WITHDRAWAL:
                return {
                    'success': False,
                    'error': f'Minimum withdrawal amount is {ServiceConfig.MIN_WITHDRAWAL}',
                    'current_balance': float(current_balance),
                    'requested': float(withdraw_amount),
                    'min_withdrawal': float(ServiceConfig.MIN_WITHDRAWAL)
                }
            
            if current_balance < withdraw_amount:
                return {
                    'success': False,
                    'error': 'Insufficient balance',
                    'current_balance': float(current_balance),
                    'requested': float(withdraw_amount)
                }
            
            # Deduct from balance
            profile = get_user_profile(user)
            if not profile:
                return {
                    'success': False,
                    'error': 'User profile not found'
                }
            
            # Determine balance field
            balance_field = None
            if hasattr(profile, 'balance'):
                balance_field = 'balance'
            elif hasattr(profile, 'coins'):
                balance_field = 'coins'
            elif hasattr(profile, 'points'):
                balance_field = 'points'
            else:
                return {
                    'success': False,
                    'error': 'No balance field found'
                }
            
            # Update balance
            current = getattr(profile, balance_field, Decimal('0'))
            setattr(profile, balance_field, safe_decimal(current) - withdraw_amount)
            profile.save(update_fields=[balance_field])
            
            # Log withdrawal
            log_transaction(
                user=user,
                amount=-withdraw_amount,
                transaction_type=TransactionType.WITHDRAWAL,
                metadata={
                    'payment_method': payment_method,
                    **(metadata or {})
                }
            )
            
            # Clear cache
            cache.delete(f"user_balance_{user.id}")
            
            new_balance = self.get_balance(user)
            
            return {
                'success': True,
                'withdrawn': float(withdraw_amount),
                'new_balance': float(new_balance),
                'payment_method': payment_method
            }
            
        except Exception as e:
            self.logger.error(f"Error processing withdrawal: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_transaction_history(
        self, 
        user: User, 
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get user's transaction history"""
        try:
            Transaction = get_transaction_model()
            if not Transaction:
                return []
            
            limit = limit or ServiceConfig.MAX_TRANSACTION_HISTORY
            
            transactions = Transaction.objects.filter(
                user=user
            ).order_by('-timestamp')[:limit]
            
            return [
                {
                    'id': t.id,
                    'amount': float(t.amount),
                    'type': t.transaction_type,
                    'timestamp': t.timestamp.isoformat(),
                    'metadata': t.metadata
                }
                for t in transactions
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting transaction history: {str(e)}")
            return []


# ============ REFERRAL SERVICE ============

class ReferralService:
    """
    Service for handling referral logic
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.wallet_service = WalletService()
    
    def get_referral_stats(self, user: User) -> Dict[str, Any]:
        """Get referral statistics for user"""
        try:
            Profile = get_profile_model()
            Transaction = get_transaction_model()
            
            if not Profile or not Transaction:
                return {
                    'total_referred': 0,
                    'total_earnings': 0,
                    'recent_referred': []
                }
            
            # Count referred users
            referred_users = Profile.objects.filter(
                referred_by=user
            ).select_related('user').count()
            
            # Calculate total referral earnings
            total_earnings = Transaction.objects.filter(
                user=user,
                transaction_type=TransactionType.REFERRAL_BONUS
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Get recent referred users
            recent = Profile.objects.filter(
                referred_by=user
            ).select_related('user').order_by('-created_at')[:5]
            
            recent_list = []
            for profile in recent:
                if hasattr(profile, 'user') and profile.user:
                    recent_list.append({
                        'username': profile.user.username,
                        'joined_at': getattr(profile, 'created_at', timezone.now()).isoformat()
                    })
            
            return {
                'total_referred': referred_users,
                'total_earnings': float(total_earnings),
                'recent_referred': recent_list
            }
            
        except Exception as e:
            self.logger.error(f"Error getting referral stats: {str(e)}", exc_info=True)
            return {
                'total_referred': 0,
                'total_earnings': 0,
                'recent_referred': []
            }
    
    @transaction.atomic
    def apply_referral_code(
        self, 
        user: User, 
        referral_code: str
    ) -> Dict[str, Any]:
        """Apply referral code to user"""
        try:
            Profile = get_profile_model()
            if not Profile:
                return {
                    'success': False,
                    'error': 'Referral system not configured'
                }
            
            # Find referrer by referral code
            referrer_profile = Profile.objects.filter(
                referral_code=referral_code
            ).select_related('user').first()
            
            if not referrer_profile or not referrer_profile.user:
                return {
                    'success': False,
                    'error': 'Invalid referral code'
                }
            
            referrer = referrer_profile.user
            
            if referrer.id == user.id:
                return {
                    'success': False,
                    'error': 'Cannot refer yourself'
                }
            
            # Check if user already has a referrer
            user_profile = get_user_profile(user)
            if not user_profile:
                return {
                    'success': False,
                    'error': 'User profile not found'
                }
            
            if hasattr(user_profile, 'referred_by') and user_profile.referred_by:
                return {
                    'success': False,
                    'error': 'User already has a referrer'
                }
            
            # Update user's profile with referrer
            if hasattr(user_profile, 'referred_by'):
                user_profile.referred_by = referrer
                user_profile.save(update_fields=['referred_by'])
                
                # Clear cache
                cache.delete(f"user_referrer_{user.id}")
                
                # Give welcome bonus to referrer (from config)
                welcome_bonus = ServiceConfig.WELCOME_BONUS
                if welcome_bonus > 0:
                    self.wallet_service.add_funds(
                        user=referrer,
                        amount=welcome_bonus,
                        reason='referral_welcome_bonus',
                        metadata={'referred_user_id': user.id, 'referred_username': user.username}
                    )
                
                return {
                    'success': True,
                    'message': f'Successfully referred by {referrer.username}',
                    'referrer': referrer.username,
                    'welcome_bonus': float(welcome_bonus) if welcome_bonus > 0 else 0
                }
            
            return {
                'success': False,
                'error': 'Profile does not support referrals'
            }
            
        except Exception as e:
            self.logger.error(f"Error applying referral code: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_referral_code(self, user: User) -> Optional[str]:
        """Generate a unique referral code for user"""
        try:
            Profile = get_profile_model()
            if not Profile:
                return None
            
            import hashlib
            import base64
            
            # Generate unique code based on user id and username
            code_string = f"{user.id}-{user.username}-{timezone.now().timestamp()}"
            hash_object = hashlib.sha256(code_string.encode())
            code = base64.b32encode(hash_object.digest())[:8].decode('utf-8').upper()
            
            # Ensure uniqueness
            while Profile.objects.filter(referral_code=code).exists():
                code = base64.b32encode(hashlib.sha256(f"{code}{timezone.now().timestamp()}".encode()).digest())[:8].decode('utf-8').upper()
            
            # Save to profile
            profile = get_user_profile(user)
            if profile and hasattr(profile, 'referral_code'):
                profile.referral_code = code
                profile.save(update_fields=['referral_code'])
                return code
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating referral code: {str(e)}")
            return None


# ============ ADMIN PROFIT SERVICE ============

class AdminProfitService:
    """
    Service for tracking admin profits
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_total_profit(self) -> Decimal:
        """Get total admin profit"""
        try:
            AdminLedger = get_admin_ledger_model()
            if not AdminLedger:
                return Decimal('0')
            
            total = AdminLedger.objects.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')
            
            return safe_decimal(total)
            
        except Exception as e:
            self.logger.error(f"Error getting total profit: {str(e)}")
            return Decimal('0')
    
    def get_profit_by_source(self, days: int = 30) -> Dict[str, float]:
        """Get profit breakdown by source for last N days"""
        try:
            AdminLedger = get_admin_ledger_model()
            if not AdminLedger:
                return {}
            
            start_date = timezone.now() - timedelta(days=days)
            
            profits = AdminLedger.objects.filter(
                timestamp__gte=start_date
            ).values('source').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            return {
                str(item['source']): float(item['total'])
                for item in profits
                if item['total'] is not None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting profit by source: {str(e)}")
            return {}
    
    def get_daily_profit(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily profit for charting"""
        try:
            AdminLedger = get_admin_ledger_model()
            if not AdminLedger:
                return []
            
            from django.db.models.functions import TruncDate
            
            start_date = timezone.now() - timedelta(days=days)
            
            daily = AdminLedger.objects.filter(
                timestamp__gte=start_date
            ).annotate(
                date=TruncDate('timestamp')
            ).values('date').annotate(
                total=Sum('amount')
            ).order_by('date')
            
            return [
                {
                    'date': item['date'].isoformat() if item['date'] else None,
                    'profit': float(item['total']) if item['total'] else 0
                }
                for item in daily
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting daily profit: {str(e)}")
            return []
    
    def get_profit_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive profit summary"""
        try:
            total = self.get_total_profit()
            by_source = self.get_profit_by_source(days)
            daily = self.get_daily_profit(days)
            
            # Calculate average daily profit
            if daily:
                avg_daily = sum(d['profit'] for d in daily) / len(daily)
            else:
                avg_daily = 0
            
            return {
                'total_profit': float(total),
                'profit_last_30_days': sum(d['profit'] for d in daily),
                'average_daily_profit': avg_daily,
                'by_source': by_source,
                'daily_breakdown': daily,
                'period_days': days
            }
            
        except Exception as e:
            self.logger.error(f"Error getting profit summary: {str(e)}")
            return {
                'total_profit': 0,
                'profit_last_30_days': 0,
                'average_daily_profit': 0,
                'by_source': {},
                'daily_breakdown': [],
                'period_days': days
            }


# ============ TASK COMPLETION SERVICE ============

class TaskCompletionService:
    """
    Service for handling task completion workflow
    """
    
    def __init__(self):
        self.verification_service = TaskVerificationService()
        self.wallet_service = WalletService()
        self.logger = logging.getLogger(__name__)
    
    @transaction.atomic
    def complete_task(
        self,
        user: User,
        task_id: int,
        proof_data: Dict = None,
        expected_revenue: Optional[Union[Decimal, float, int, str]] = None
    ) -> Dict[str, Any]:
        """
        Complete a task and create pending completion
        """
        try:
            # Get task
            try:
                task = MasterTask.objects.get(id=task_id, is_active=True)
            except MasterTask.DoesNotExist:
                return {
                    'success': False,
                    'error': 'Task not found or inactive'
                }
            
            # Check availability
            is_available, reason = task.is_available_with_cooldown(
                user_level=getattr(user, 'level', 1),
                user_id=user.id
            )
            
            if not is_available:
                return {
                    'success': False,
                    'error': reason or 'Task not available'
                }
            
            # Create completion record
            completion = UserTaskCompletion.objects.create(
                user=user,
                task=task,
                status='pending_verification',
                proof_data=proof_data or {},
                ip_address=getattr(user, 'last_ip', None),
                user_agent=getattr(user, 'user_agent', '')
            )
            
            result = {
                'success': True,
                'completion_id': completion.id,
                'status': 'pending_verification',
                'message': 'Task submitted for verification'
            }
            
            # If revenue is known immediately, process it
            if expected_revenue is not None:
                revenue = safe_decimal(expected_revenue)
                if revenue > 0:
                    # Auto-verify for tasks with immediate revenue
                    verify_result = self.verification_service.verify_and_distribute(
                        completion=completion,
                        actual_revenue=revenue,
                        verified_by='system_auto',
                        metadata={'auto_verified': True}
                    )
                    
                    result['verification'] = verify_result
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in complete_task: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }