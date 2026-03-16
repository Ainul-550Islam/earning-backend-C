# wallet/signals.py
from django.db.models.signals import post_save, pre_save, pre_delete, m2m_changed
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache
import logging
from decimal import Decimal, InvalidOperation

from .models import Wallet, WalletTransaction, UserPaymentMethod, Withdrawal, WalletWebhookLog
from .tasks import send_wallet_notification

logger = logging.getLogger(__name__)
User = get_user_model()


def safe_task(task_func, *args, **kwargs):
    """Celery task কে safely call করে — Celery না থাকলে skip"""
    try:
        task_func.delay(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Task call failed (non-critical): {e}")


def safe_cache_delete(key):
    """Cache delete safely — সব backend এ কাজ করে"""
    try:
        cache.delete(key)
    except Exception:
        pass


def safe_cache_delete_pattern(pattern):
    """Pattern delete safely — Redis না থাকলে skip"""
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
    except Exception:
        pass


# ============================================
# WALLET SIGNALS
# ============================================

@receiver(post_save, sender=User)  # ✅ FIX 1: @receiver decorator যোগ করা হয়েছে
def create_user_wallet(sender, instance, created, **kwargs):
    """Signal: ইউজার ক্রিয়েট হলে অটোমেটিক ওয়ালেট তৈরি"""
    if not created:
        return

    try:
        if Wallet.objects.filter(user=instance).exists():
            logger.debug(f"Wallet already exists for user {instance.id}")
            return

        with transaction.atomic():
            wallet = Wallet.objects.create(
                user=instance,
                currency='BDT',
                current_balance=Decimal('0'),
                pending_balance=Decimal('0'),
                total_earned=Decimal('0'),
                total_withdrawn=Decimal('0')
            )
            logger.info(f"Created wallet for new user: {instance.username}")

            # ✅ FIX 2: Celery task safely call
            safe_task(
                send_wallet_notification,
                instance.id,
                'wallet_created',
                {'balance': 0, 'currency': 'BDT'}
            )

    except Exception as e:
        logger.error(f"Failed to create wallet for user {instance.id}: {e}", exc_info=True)


@receiver(pre_save, sender=Wallet)
def validate_wallet_balance(sender, instance, **kwargs):
    """Signal: ওয়ালেট সেভ করার আগে ব্যালেন্স ভ্যালিডেশন"""
    try:
        if instance.current_balance < 0:
            instance.current_balance = Decimal('0')
        if instance.pending_balance < 0:
            instance.pending_balance = Decimal('0')
        if instance.frozen_balance < 0:
            instance.frozen_balance = Decimal('0')
        if instance.bonus_balance < 0:
            instance.bonus_balance = Decimal('0')
        if instance.frozen_balance > instance.current_balance:
            instance.frozen_balance = instance.current_balance
    except (InvalidOperation, TypeError) as e:
        logger.error(f"Invalid balance values for wallet {instance.id}: {e}")
        instance.current_balance = Decimal('0')
        instance.frozen_balance = Decimal('0')
        instance.bonus_balance = Decimal('0')


@receiver(post_save, sender=Wallet)
def handle_wallet_status_change(sender, instance, created, **kwargs):
    """Signal: ওয়ালেট স্ট্যাটাস চেঞ্জ হলে হ্যান্ডেল করা"""
    if not created:
        try:
            original = Wallet.objects.get(id=instance.id)

            if original.is_locked != instance.is_locked:
                if instance.is_locked:
                    logger.warning(f"Wallet {instance.id} locked: {instance.locked_reason}")
                    safe_task(send_wallet_notification, instance.user.id, 'wallet_locked', {
                        'reason': instance.locked_reason,
                        'locked_at': instance.locked_at.isoformat() if instance.locked_at else None
                    })
                else:
                    logger.info(f"Wallet {instance.id} unlocked")
                    safe_task(send_wallet_notification, instance.user.id, 'wallet_unlocked', {})

            if instance.current_balance < Decimal('50.00'):
                cache_key = f"low_balance_warning_{instance.user.id}_{timezone.now().date()}"
                if not cache.get(cache_key):
                    safe_task(send_wallet_notification, instance.user.id, 'low_balance', {
                        'balance': float(instance.current_balance),
                        'currency': instance.currency
                    })
                    cache.set(cache_key, True, 86400)

        except Wallet.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error in wallet status change handler: {e}")
    try:
        from api.cache.integration import invalidate_wallet_cache
        invalidate_wallet_cache(instance.user_id)
    except Exception:
        pass


# ============================================
# WALLETTRANSACTION SIGNALS
# ============================================

@receiver(pre_save, sender=WalletTransaction)
def set_transaction_balances(sender, instance, **kwargs):
    """Signal: ট্রানজেকশন সেভ করার আগে ব্যালেন্স সেট করা"""
    try:
        if not instance.balance_before and instance.wallet:
            instance.balance_before = instance.wallet.current_balance
        if instance.status == 'approved' and not instance.balance_after and instance.wallet:
            instance.balance_after = instance.wallet.current_balance + instance.amount
    except Exception as e:
        logger.error(f"Error setting transaction balances: {e}")


@receiver(post_save, sender=WalletTransaction)
def handle_transaction_status_change(sender, instance, created, **kwargs):
    """Signal: ট্রানজেকশন স্ট্যাটাস চেঞ্জ হলে হ্যান্ডেল করা"""
    try:
        if not created:
            original = WalletTransaction.objects.get(id=instance.id)
            if original.status != instance.status:
                # logger.info(f"Transaction {instance.walletTransaction_id} status: {original.status} -> {instance.status}")
                tx_id = getattr(instance, 'walletTransaction_id', instance.id)
                logger.info(f"Transaction {tx_id} status: {original.status} -> {instance.status}")

                if instance.status == 'approved':
                    safe_task(send_wallet_notification, instance.wallet.user.id, 'transaction_approved', {
                        'transaction_id': str(instance.walletTransaction_id),
                        'amount': float(instance.amount),
                        'type': instance.type,
                        'new_balance': float(instance.balance_after) if instance.balance_after else 0
                    })
                elif instance.status == 'rejected':
                    safe_task(send_wallet_notification, instance.wallet.user.id, 'transaction_rejected', {
                        'transaction_id': str(instance.walletTransaction_id),
                        'amount': float(instance.amount),
                        'type': instance.type,
                    })
                elif instance.status == 'reversed':
                    safe_task(send_wallet_notification, instance.wallet.user.id, 'transaction_reversed', {
                        'transaction_id': str(instance.walletTransaction_id),
                        'amount': float(instance.amount),
                    })

    except WalletTransaction.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error in transaction status change handler: {e}")
    try:
        if instance.wallet_id:
            from api.cache.integration import invalidate_wallet_cache
            invalidate_wallet_cache(instance.wallet.user_id)
    except Exception:
        pass


# ============================================
# USERPAYMENTMETHOD SIGNALS
# ============================================

@receiver(pre_save, sender=UserPaymentMethod)
def handle_primary_payment_method(sender, instance, **kwargs):
    """Signal: প্রাইমারি পেমেন্ট মেথড ম্যানেজ করা"""
    try:
        if instance.is_primary and instance.user:
            with transaction.atomic():
                UserPaymentMethod.objects.filter(
                    user=instance.user,
                    is_primary=True
                ).exclude(id=instance.id).update(is_primary=False)
    except Exception as e:
        logger.error(f"Error handling primary payment method: {e}")


@receiver(post_save, sender=UserPaymentMethod)
def handle_payment_method_verification(sender, instance, created, **kwargs):
    """Signal: পেমেন্ট মেথড ভেরিফাই হলে হ্যান্ডেল করা"""
    try:
        if not created and instance.is_verified:
            original = UserPaymentMethod.objects.get(id=instance.id)
            if not original.is_verified and instance.is_verified:
                logger.info(f"Payment method {instance.id} verified")
                safe_task(send_wallet_notification, instance.user.id, 'payment_method_verified', {
                    'method_type': instance.get_method_type_display(),
                    'account_ending': instance.account_number[-4:] if len(instance.account_number) >= 4 else instance.account_number
                })
    except UserPaymentMethod.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error in payment method verification handler: {e}")


# ============================================
# WITHDRAWAL SIGNALS
# ============================================

@receiver(pre_save, sender=Withdrawal)
def calculate_withdrawal_net_amount(sender, instance, **kwargs):
    """Signal: উইথড্রয়ালের নেট অ্যামাউন্ট ক্যালকুলেট করা"""
    try:
        if instance.amount and instance.fee is not None:
            instance.net_amount = instance.amount - instance.fee
    except (InvalidOperation, TypeError) as e:
        logger.error(f"Error calculating withdrawal net amount: {e}")
        instance.net_amount = Decimal('0')


@receiver(post_save, sender=Withdrawal)
def handle_withdrawal_status_change(sender, instance, created, **kwargs):
    """Signal: উইথড্রয়াল স্ট্যাটাস চেঞ্জ হলে হ্যান্ডেল করা"""
    try:
        if not created:
            original = Withdrawal.objects.get(id=instance.id)
            if original.status != instance.status:
                logger.info(f"Withdrawal {instance.withdrawal_id} status: {original.status} -> {instance.status}")

                if instance.status == 'completed':
                    safe_task(send_wallet_notification, instance.user.id, 'withdrawal_success', {
                        'withdrawal_id': str(instance.withdrawal_id),
                        'amount': float(instance.amount),
                        'net_amount': float(instance.net_amount),
                    })
                elif instance.status in ['rejected', 'failed']:
                    safe_task(send_wallet_notification, instance.user.id, 'withdrawal_failed', {
                        'withdrawal_id': str(instance.withdrawal_id),
                        'amount': float(instance.amount),
                        'reason': getattr(instance, 'rejection_reason', 'Processing failed') or 'Unknown',
                    })

    except Withdrawal.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error in withdrawal status change handler: {e}")


# ============================================
# WALLETWEBHOOKLOG SIGNALS
# ============================================

@receiver(post_save, sender=WalletWebhookLog)
def handle_webhook_processing(sender, instance, created, **kwargs):
    """Signal: ওয়েবহুক প্রসেস হলে হ্যান্ডেল করা"""
    if created and not instance.is_processed:
        try:
            from .tasks import process_webhook_async
            process_webhook_async.delay(instance.id)
            logger.info(f"Queued webhook {instance.id} for async processing")
        except Exception as e:
            logger.error(f"Failed to queue webhook {instance.id}: {e}")


# ============================================
# BULK OPERATION SIGNALS
# ============================================

@receiver(m2m_changed)
def handle_bulk_operations(sender, instance, action, **kwargs):
    """Signal: বাল্ক অপারেশনের সময় ক্যাশ ক্লিয়ার"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # ✅ FIX 3: safe pattern delete — Redis না থাকলে crash করবে না
        safe_cache_delete_pattern('wallet_stats_*')
        safe_cache_delete_pattern('user_wallet_*')
        safe_cache_delete_pattern('transaction_summary_*')
        logger.debug(f"Cleared caches after bulk {action} on {sender}")




# # wallet/signals.py
# from django.db.models.signals import post_save, pre_save, pre_delete, m2m_changed
# from django.dispatch import receiver
# from django.db import transaction
# from django.utils import timezone
# from django.contrib.auth import get_user_model
# from django.conf import settings
# from django.core.cache import cache
# import logging
# from decimal import Decimal, InvalidOperation

# from .models import Wallet, WalletTransaction, UserPaymentMethod, Withdrawal, WalletWebhookLog
# from .tasks import send_wallet_notification

# logger = logging.getLogger(__name__)


# # ============================================
# # WALLET SIGNALS
# # ============================================

# def create_user_wallet(sender, instance, created, **kwargs):
#     """
#     Signal: ইউজার ক্রিয়েট হলে অটোমেটিক ওয়ালেট তৈরি
#     """
#     if not created:
#         return  # Only create wallet for new users
    
#     try:
#         # Check if wallet already exists (prevent duplicates)
#         if Wallet.objects.filter(user=instance).exists():
#             logger.debug(f"Wallet already exists for user {instance.id}, skipping creation")
#             return
        
#         with transaction.atomic():
#             wallet = Wallet.objects.create(
#                 user=instance,
#                 currency='BDT',
#                 current_balance=Decimal('0'),
#                 pending_balance=Decimal('0'),
#                 total_earned=Decimal('0'),
#                 total_withdrawn=Decimal('0')
#             )
            
#             logger.info(f"✅ Created wallet for new user: {instance.username} (ID: {instance.id})")
            
#             # Send welcome notification (only if celery is available)
#             try:
#                 send_wallet_notification.delay(
#                     instance.id,
#                     'wallet_created',
#                     {
#                         'balance': 0,
#                         'currency': 'BDT'
#                     }
#                 )
#             except Exception as notify_error:
#                 logger.warning(f"Could not send wallet notification: {notify_error}")
                
#     except Exception as e:
#         logger.error(f"❌ Failed to create wallet for user {instance.id}: {e}", exc_info=True)
#         # Don't raise - user creation should succeed even if wallet creation fails


# @receiver(pre_save, sender=Wallet)
# def validate_wallet_balance(sender, instance, **kwargs):
#     """
#     Signal: ওয়ালেট সেভ করার আগে ব্যালেন্স ভ্যালিডেশন
#     """
#     try:
#         # Ensure balances are not negative
#         if instance.current_balance < 0:
#             logger.warning(
#                 f"Attempt to set negative current balance for wallet {instance.id}: "
#                 f"{instance.current_balance}"
#             )
#             instance.current_balance = Decimal('0')
        
#         if instance.pending_balance < 0:
#             instance.pending_balance = Decimal('0')
        
#         if instance.frozen_balance < 0:
#             instance.frozen_balance = Decimal('0')
        
#         if instance.bonus_balance < 0:
#             instance.bonus_balance = Decimal('0')
        
#         # Ensure frozen balance doesn't exceed current balance
#         if instance.frozen_balance > instance.current_balance:
#             logger.warning(
#                 f"Frozen balance exceeds current balance for wallet {instance.id}. "
#                 f"Adjusting frozen balance."
#             )
#             instance.frozen_balance = instance.current_balance
        
#     except (InvalidOperation, TypeError) as e:
#         logger.error(f"Invalid balance values for wallet {instance.id}: {e}")
#         # Reset to safe defaults
#         instance.current_balance = Decimal('0')
#         instance.frozen_balance = Decimal('0')
#         instance.bonus_balance = Decimal('0')


# @receiver(post_save, sender=Wallet)
# def handle_wallet_status_change(sender, instance, created, **kwargs):
#     """
#     Signal: ওয়ালেট স্ট্যাটাস চেঞ্জ হলে হ্যান্ডেল করা
#     """
#     if not created:
#         try:
#             # Check if wallet was just locked/unlocked
#             original = Wallet.objects.get(id=instance.id)
            
#             if original.is_locked != instance.is_locked:
#                 if instance.is_locked:
#                     # Wallet was locked
#                     logger.warning(f"Wallet {instance.id} locked: {instance.locked_reason}")
                    
#                     send_wallet_notification.delay(
#                         instance.user.id,
#                         'wallet_locked',
#                         {
#                             'reason': instance.locked_reason,
#                             'locked_at': instance.locked_at.isoformat() if instance.locked_at else None
#                         }
#                     )
#                 else:
#                     # Wallet was unlocked
#                     logger.info(f"Wallet {instance.id} unlocked")
                    
#                     send_wallet_notification.delay(
#                         instance.user.id,
#                         'wallet_unlocked',
#                         {}
#                     )
            
#             # Check for low balance
#             if instance.current_balance < Decimal('50.00'):
#                 # Send low balance warning (but only once per day)
#                 cache_key = f"low_balance_warning_{instance.user.id}_{timezone.now().date()}"
#                 if not cache.get(cache_key):
#                     send_wallet_notification.delay(
#                         instance.user.id,
#                         'low_balance',
#                         {
#                             'balance': float(instance.current_balance),
#                             'currency': instance.currency
#                         }
#                     )
#                     cache.set(cache_key, True, 86400)  # 24 hours
            
#         except Wallet.DoesNotExist:
#             pass  # New wallet, no original to compare
#         except Exception as e:
#             logger.error(f"Error in wallet status change handler: {e}")


# # ============================================
# # WALLETTRANSACTION SIGNALS
# # ============================================

# @receiver(pre_save, sender=WalletTransaction)
# def set_transaction_balances(sender, instance, **kwargs):
#     """
#     Signal: ট্রানজেকশন সেভ করার আগে ব্যালেন্স সেট করা
#     """
#     try:
#         if not instance.balance_before and instance.wallet:
#             instance.balance_before = instance.wallet.current_balance
        
#         # If transaction is being approved, set balance_after
#         if instance.status == 'approved' and not instance.balance_after and instance.wallet:
#             if instance.amount > 0:
#                 instance.balance_after = instance.wallet.current_balance + instance.amount
#             else:
#                 instance.balance_after = instance.wallet.current_balance + instance.amount  # amount is negative
        
#     except Exception as e:
#         logger.error(f"Error setting transaction balances: {e}")


# @receiver(post_save, sender=WalletTransaction)
# def handle_transaction_status_change(sender, instance, created, **kwargs):
#     """
#     Signal: ট্রানজেকশন স্ট্যাটাস চেঞ্জ হলে হ্যান্ডেল করা
#     """
#     try:
#         if not created:
#             # Get original status
#             original = WalletTransaction.objects.get(id=instance.id)
            
#             # Check if status changed
#             if original.status != instance.status:
#                 logger.info(
#                     f"Transaction {instance.transaction_id} status changed: "
#                     f"{original.status} -> {instance.status}"
#                 )
                
#                 # Send notification based on status
#                 if instance.status == 'approved':
#                     send_wallet_notification.delay(
#                         instance.wallet.user.id,
#                         'transaction_approved',
#                         {
#                             'transaction_id': str(instance.transaction_id),
#                             'amount': float(instance.amount),
#                             'type': instance.type,
#                             'new_balance': float(instance.balance_after) if instance.balance_after else 0
#                         }
#                     )
                
#                 elif instance.status == 'rejected':
#                     send_wallet_notification.delay(
#                         instance.wallet.user.id,
#                         'transaction_rejected',
#                         {
#                             'transaction_id': str(instance.transaction_id),
#                             'amount': float(instance.amount),
#                             'type': instance.type,
#                             'reason': instance.description.split('Rejected: ')[-1] if 'Rejected:' in instance.description else 'Unknown'
#                         }
#                     )
                
#                 elif instance.status == 'reversed':
#                     send_wallet_notification.delay(
#                         instance.wallet.user.id,
#                         'transaction_reversed',
#                         {
#                             'transaction_id': str(instance.transaction_id),
#                             'amount': float(instance.amount),
#                             'reversal_id': str(instance.reversed_by.transaction_id) if instance.reversed_by else None
#                         }
#                     )
        
#     except WalletTransaction.DoesNotExist:
#         pass  # New transaction
#     except Exception as e:
#         logger.error(f"Error in transaction status change handler: {e}")


# # ============================================
# # USERPAYMENTMETHOD SIGNALS
# # ============================================

# @receiver(pre_save, sender=UserPaymentMethod)
# def handle_primary_payment_method(sender, instance, **kwargs):
#     """
#     Signal: প্রাইমারি পেমেন্ট মেথড ম্যানেজ করা
#     """
#     try:
#         if instance.is_primary and instance.user:
#             # Ensure only one primary method per user
#             with transaction.atomic():
#                 UserPaymentMethod.objects.filter(
#                     user=instance.user,
#                     is_primary=True
#                 ).exclude(id=instance.id).update(is_primary=False)
    
#     except Exception as e:
#         logger.error(f"Error handling primary payment method: {e}")


# @receiver(post_save, sender=UserPaymentMethod)
# def handle_payment_method_verification(sender, instance, created, **kwargs):
#     """
#     Signal: পেমেন্ট মেথড ভেরিফাই হলে হ্যান্ডেল করা
#     """
#     try:
#         if not created and instance.is_verified:
#             # Check if it was just verified
#             original = UserPaymentMethod.objects.get(id=instance.id)
            
#             if not original.is_verified and instance.is_verified:
#                 logger.info(f"Payment method {instance.id} verified for user {instance.user.username}")
                
#                 send_wallet_notification.delay(
#                     instance.user.id,
#                     'payment_method_verified',
#                     {
#                         'method_type': instance.get_method_type_display(),
#                         'account_ending': instance.account_number[-4:] if len(instance.account_number) >= 4 else instance.account_number
#                     }
#                 )
    
#     except UserPaymentMethod.DoesNotExist:
#         pass  # New payment method
#     except Exception as e:
#         logger.error(f"Error in payment method verification handler: {e}")


# # ============================================
# # WITHDRAWAL SIGNALS
# # ============================================

# @receiver(pre_save, sender=Withdrawal)
# def calculate_withdrawal_net_amount(sender, instance, **kwargs):
#     """
#     Signal: উইথড্রয়ালের নেট অ্যামাউন্ট ক্যালকুলেট করা
#     """
#     try:
#         if instance.amount and instance.fee is not None:
#             instance.net_amount = instance.amount - instance.fee
#     except (InvalidOperation, TypeError) as e:
#         logger.error(f"Error calculating withdrawal net amount: {e}")
#         instance.net_amount = Decimal('0')


# @receiver(post_save, sender=Withdrawal)
# def handle_withdrawal_status_change(sender, instance, created, **kwargs):
#     """
#     Signal: উইথড্রয়াল স্ট্যাটাস চেঞ্জ হলে হ্যান্ডেল করা
#     """
#     try:
#         if not created:
#             # Get original status
#             original = Withdrawal.objects.get(id=instance.id)
            
#             # Check if status changed
#             if original.status != instance.status:
#                 logger.info(
#                     f"Withdrawal {instance.withdrawal_id} status changed: "
#                     f"{original.status} -> {instance.status}"
#                 )
                
#                 # Send notification based on status
#                 if instance.status == 'completed':
#                     send_wallet_notification.delay(
#                         instance.user.id,
#                         'withdrawal_success',
#                         {
#                             'withdrawal_id': str(instance.withdrawal_id),
#                             'amount': float(instance.amount),
#                             'net_amount': float(instance.net_amount),
#                             'processed_at': instance.processed_at.isoformat() if instance.processed_at else None,
#                             'payment_method': instance.payment_method.get_method_type_display() if instance.payment_method else 'Unknown'
#                         }
#                     )
                
#                 elif instance.status == 'rejected':
#                     send_wallet_notification.delay(
#                         instance.user.id,
#                         'withdrawal_failed',
#                         {
#                             'withdrawal_id': str(instance.withdrawal_id),
#                             'amount': float(instance.amount),
#                             'reason': instance.rejection_reason or 'Unknown',
#                             'rejected_at': instance.rejected_at.isoformat() if instance.rejected_at else None
#                         }
#                     )
                
#                 elif instance.status == 'failed':
#                     send_wallet_notification.delay(
#                         instance.user.id,
#                         'withdrawal_failed',
#                         {
#                             'withdrawal_id': str(instance.withdrawal_id),
#                             'amount': float(instance.amount),
#                             'reason': 'Processing failed',
#                             'failed_at': timezone.now().isoformat()
#                         }
#                     )
    
#     except Withdrawal.DoesNotExist:
#         pass  # New withdrawal
#     except Exception as e:
#         logger.error(f"Error in withdrawal status change handler: {e}")


# # ============================================
# # WALLETWEBHOOKLOG SIGNALS
# # ============================================

# @receiver(post_save, sender=WalletWebhookLog)
# def handle_webhook_processing(sender, instance, created, **kwargs):
#     """
#     Signal: ওয়েবহুক প্রসেস হলে হ্যান্ডেল করা
#     """
#     if created and not instance.is_processed:
#         try:
#             # Process webhook asynchronously
#             from .tasks import process_webhook_async
#             process_webhook_async.delay(instance.id)
            
#             logger.info(f"Queued webhook {instance.id} for async processing")
            
#         except Exception as e:
#             logger.error(f"Failed to queue webhook {instance.id} for processing: {e}")
#             instance.processing_error = str(e)
#             instance.save()


# # ============================================
# # BULK OPERATION SIGNALS
# # ============================================

# @receiver(m2m_changed)
# def handle_bulk_operations(sender, instance, action, **kwargs):
#     """
#     Signal: বাল্ক অপারেশনের সময় পারফরম্যান্স অপ্টিমাইজেশন
#     """
#     if action in ['post_add', 'post_remove', 'post_clear']:
#         # Clear relevant caches
#         cache_keys_to_clear = [
#             'wallet_stats_*',
#             'user_wallet_*',
#             'transaction_summary_*'
#         ]
        
#         for key in cache_keys_to_clear:
#             cache.delete_pattern(key)  # Requires redis or similar cache backend
        
#         logger.debug(f"Cleared caches after bulk {action} operation on {sender}")


# # ============================================
# # ERROR HANDLING SIGNAL
# # ============================================

# @receiver(post_save)
# def log_model_changes(sender, instance, created, **kwargs):
#     """
#     Signal: সব মডেল চেঞ্জ লগ করা (ডিবাগিং/অডিটিং এর জন্য)
#     """
#     # Skip logging for certain models
#     if sender.__name__ in ['Session', 'LogEntry']:
#         return
    
#     try:
#         action = "created" if created else "updated"
        
#         logger.debug(
#             f"Model {sender.__name__} {action}: {instance}",
#             extra={
#                 'model': sender.__name__,
#                 'action': action,
#                 'instance_id': getattr(instance, 'id', None),
#                 'user': getattr(instance, 'user_id', None)
#             }
#         )
        
#     except Exception as e:
#         # Don't let logging errors crash the application
#         pass