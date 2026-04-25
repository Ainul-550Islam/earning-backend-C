"""
Auto Refill Tasks

Check wallet balance and trigger refill
when threshold is reached.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from ..models.billing import AdvertiserWallet
try:
    from ..services import AutoRefillService
except ImportError:
    AutoRefillService = None
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.check_auto_refill")
def check_auto_refill():
    """
    Check all wallets for auto-refill eligibility.
    
    This task runs every 5 minutes to check if any wallets
    have reached their refill threshold and should trigger auto-refill.
    """
    try:
        refill_service = AutoRefillService()
        billing_service = AdvertiserBillingService()
        
        # Get all wallets with auto-refill enabled
        auto_refill_wallets = AdvertiserWallet.objects.filter(
            auto_refill_enabled=True,
            is_active=True,
            is_suspended=False
        ).select_related('advertiser')
        
        wallets_checked = auto_refill_wallets.count()
        refills_triggered = 0
        refills_failed = 0
        
        for wallet in auto_refill_wallets:
            try:
                # Get current balance
                current_balance = billing_service.get_wallet_balance(wallet.advertiser)
                available_balance = current_balance.get('available_balance', 0)
                
                # Check if refill should be triggered
                if available_balance <= wallet.auto_refill_threshold:
                    logger.info(f"Auto-refill triggered for advertiser {wallet.advertiser.id}: {available_balance} <= {wallet.auto_refill_threshold}")
                    
                    # Check if recently refilled (avoid duplicate refills)
                    if _should_refill(wallet):
                        # Trigger auto-refill
                        refill_result = refill_service.process_auto_refill(wallet)
                        
                        if refill_result.get('success'):
                            refills_triggered += 1
                            logger.info(f"Auto-refill successful for advertiser {wallet.advertiser.id}: ${refill_result.get('amount', 0):.2f}")
                            
                            # Send refill notification
                            _send_refill_notification(wallet, refill_result)
                        else:
                            refills_failed += 1
                            logger.error(f"Auto-refill failed for advertiser {wallet.advertiser.id}: {refill_result.get('error', 'Unknown error')}")
                            
                            # Send refill failure notification
                            _send_refill_failure_notification(wallet, refill_result)
                    else:
                        logger.info(f"Auto-refill skipped for advertiser {wallet.advertiser.id}: recently refilled")
                
                # Check if approaching threshold (warning)
                elif available_balance <= (wallet.auto_refill_threshold * 1.2):  # 20% above threshold
                    logger.warning(f"Wallet approaching refill threshold for advertiser {wallet.advertiser.id}: {available_balance}")
                    
                    # Send approaching threshold notification
                    _send_approaching_threshold_notification(wallet, available_balance)
                
            except Exception as e:
                logger.error(f"Error checking auto-refill for wallet {wallet.id}: {e}")
                continue
        
        logger.info(f"Auto-refill check completed: {wallets_checked} wallets checked, {refills_triggered} refills triggered, {refills_failed} refills failed")
        
        return {
            'wallets_checked': wallets_checked,
            'refills_triggered': refills_triggered,
            'refills_failed': refills_failed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in auto-refill check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.validate_auto_refill_config")
def validate_auto_refill_config():
    """
    Validate auto-refill configurations.
    
    This task runs daily to check for invalid or
    problematic auto-refill configurations.
    """
    try:
        refill_service = AutoRefillService()
        
        # Get all wallets with auto-refill enabled
        auto_refill_wallets = AdvertiserWallet.objects.filter(
            auto_refill_enabled=True
        ).select_related('advertiser')
        
        configurations_checked = auto_refill_wallets.count()
        invalid_configs = 0
        warnings = 0
        
        for wallet in auto_refill_wallets:
            try:
                # Validate configuration
                validation_result = refill_service.validate_auto_refill_config(wallet)
                
                if not validation_result.get('valid', True):
                    invalid_configs += 1
                    logger.warning(f"Invalid auto-refill config for advertiser {wallet.advertiser.id}: {validation_result.get('errors', [])}")
                    
                    # Send configuration error notification
                    _send_config_error_notification(wallet, validation_result.get('errors', []))
                
                # Check for warnings
                if validation_result.get('warnings', []):
                    warnings += len(validation_result['warnings'])
                    logger.warning(f"Auto-refill warnings for advertiser {wallet.advertiser.id}: {validation_result.get('warnings', [])}")
                    
                    # Send configuration warning notification
                    _send_config_warning_notification(wallet, validation_result.get('warnings', []))
                
            except Exception as e:
                logger.error(f"Error validating auto-refill config for wallet {wallet.id}: {e}")
                continue
        
        logger.info(f"Auto-refill config validation completed: {configurations_checked} configurations checked, {invalid_configs} invalid, {warnings} warnings")
        
        return {
            'configurations_checked': configurations_checked,
            'invalid_configs': invalid_configs,
            'warnings': warnings,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in auto-refill config validation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_refill_history")
def update_refill_history():
    """
    Update refill history and statistics.
    
    This task runs daily to update refill statistics
    and maintain refill history records.
    """
    try:
        refill_service = AutoRefillService()
        
        # Get refill history for the last day
        yesterday = timezone.now() - timezone.timedelta(days=1)
        
        refill_history = refill_service.get_refill_history(
            start_date=yesterday.date(),
            end_date=timezone.now().date()
        )
        
        # Update statistics
        total_refills = len(refill_history)
        total_amount = sum(refill.get('amount', 0) for refill in refill_history)
        successful_refills = len([r for r in refill_history if r.get('status') == 'success'])
        failed_refills = total_refills - successful_refills
        
        # Store daily statistics
        _store_daily_refill_stats(yesterday.date(), {
            'total_refills': total_refills,
            'total_amount': total_amount,
            'successful_refills': successful_refills,
            'failed_refills': failed_refills,
            'success_rate': (successful_refills / total_refills * 100) if total_refills > 0 else 0,
        })
        
        logger.info(f"Refill history update completed: {total_refills} refills, ${total_amount:.2f} total amount")
        
        return {
            'date': yesterday.date().isoformat(),
            'total_refills': total_refills,
            'total_amount': total_amount,
            'successful_refills': successful_refills,
            'failed_refills': failed_refills,
            'success_rate': (successful_refills / total_refills * 100) if total_refills > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in refill history update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_refill_logs")
def cleanup_refill_logs():
    """
    Clean up old refill logs and records.
    
    This task runs weekly to clean up old refill
    logs and maintain database performance.
    """
    try:
        refill_service = AutoRefillService()
        
        # Clean up logs older than 90 days
        cutoff_date = timezone.now() - timezone.timedelta(days=90)
        
        # This would implement actual cleanup logic
        # For example, archive or delete old refill records
        logs_cleaned = refill_service.cleanup_old_refill_logs(cutoff_date)
        
        logger.info(f"Refill log cleanup completed: {logs_cleaned} logs cleaned")
        
        return {
            'cutoff_date': cutoff_date.date().isoformat(),
            'logs_cleaned': logs_cleaned,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in refill log cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_refill_payment_methods")
def check_refill_payment_methods():
    """
    Check validity of refill payment methods.
    
    This task runs daily to check if payment methods
    used for auto-refill are still valid.
    """
    try:
        refill_service = AutoRefillService()
        
        # Get all wallets with auto-refill enabled
        auto_refill_wallets = AdvertiserWallet.objects.filter(
            auto_refill_enabled=True
        ).select_related('advertiser')
        
        payment_methods_checked = auto_refill_wallets.count()
        invalid_methods = 0
        
        for wallet in auto_refill_wallets:
            try:
                # Check payment method validity
                payment_method = wallet.auto_refill_payment_method
                payment_token = wallet.auto_refill_payment_token
                
                if not payment_method or not payment_token:
                    invalid_methods += 1
                    logger.warning(f"Missing payment method for auto-refill: advertiser {wallet.advertiser.id}")
                    
                    # Send missing payment method notification
                    _send_missing_payment_notification(wallet)
                    continue
                
                # Validate payment method
                validation_result = refill_service.validate_payment_method(payment_method, payment_token)
                
                if not validation_result.get('valid', True):
                    invalid_methods += 1
                    logger.warning(f"Invalid payment method for auto-refill: advertiser {wallet.advertiser.id}")
                    
                    # Send invalid payment method notification
                    _send_invalid_payment_notification(wallet, validation_result.get('error', 'Unknown error'))
                
            except Exception as e:
                logger.error(f"Error checking payment method for wallet {wallet.id}: {e}")
                continue
        
        logger.info(f"Payment method check completed: {payment_methods_checked} methods checked, {invalid_methods} invalid")
        
        return {
            'payment_methods_checked': payment_methods_checked,
            'invalid_methods': invalid_methods,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in payment method check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _should_refill(wallet):
    """Check if wallet should be refilled (avoid duplicates)."""
    try:
        # Check if recently refilled (within last hour)
        recent_refill_time = timezone.now() - timezone.timedelta(hours=1)
        
        # This would check actual refill history
        # For now, return True (allow refill)
        return True
        
    except Exception as e:
        logger.error(f"Error checking if should refill: {e}")
        return False


def _send_refill_notification(wallet, refill_result):
    """Send refill success notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_success',
            'title': 'Auto Refill Successful',
            'message': f'Your wallet has been automatically refilled with ${refill_result.get("amount", 0):.2f}',
            'data': {
                'amount': refill_result.get('amount', 0),
                'new_balance': refill_result.get('new_balance', 0),
                'payment_method': refill_result.get('payment_method'),
                'refilled_at': refill_result.get('refilled_at'),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending refill notification: {e}")


def _send_refill_failure_notification(wallet, refill_result):
    """Send refill failure notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_failed',
            'title': 'Auto Refill Failed',
            'message': f'Your auto-refill has failed: {refill_result.get("error", "Unknown error")}',
            'data': {
                'error': refill_result.get('error', 'Unknown error'),
                'amount_attempted': refill_result.get('amount_attempted', 0),
                'payment_method': refill_result.get('payment_method'),
                'failed_at': refill_result.get('failed_at'),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending refill failure notification: {e}")


def _send_approaching_threshold_notification(wallet, available_balance):
    """Send approaching threshold notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_approaching',
            'title': 'Auto Refill Threshold Approaching',
            'message': f'Your wallet balance is approaching the auto-refill threshold. Current balance: ${available_balance:.2f}',
            'data': {
                'current_balance': available_balance,
                'threshold': wallet.auto_refill_threshold,
                'refill_amount': wallet.auto_refill_amount,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending approaching threshold notification: {e}")


def _send_config_error_notification(wallet, errors):
    """Send configuration error notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_config_error',
            'title': 'Auto Refill Configuration Error',
            'message': f'There are errors in your auto-refill configuration: {", ".join(errors)}',
            'data': {
                'errors': errors,
                'threshold': wallet.auto_refill_threshold,
                'amount': wallet.auto_refill_amount,
                'payment_method': wallet.auto_refill_payment_method,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending config error notification: {e}")


def _send_config_warning_notification(wallet, warnings):
    """Send configuration warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_config_warning',
            'title': 'Auto Refill Configuration Warning',
            'message': f'There are warnings in your auto-refill configuration: {", ".join(warnings)}',
            'data': {
                'warnings': warnings,
                'threshold': wallet.auto_refill_threshold,
                'amount': wallet.auto_refill_amount,
                'payment_method': wallet.auto_refill_payment_method,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending config warning notification: {e}")


def _send_missing_payment_notification(wallet):
    """Send missing payment method notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_missing_payment',
            'title': 'Auto Refill Payment Method Missing',
            'message': 'Your auto-refill is enabled but no payment method is configured. Please configure a payment method to continue.',
            'data': {
                'threshold': wallet.auto_refill_threshold,
                'amount': wallet.auto_refill_amount,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending missing payment notification: {e}")


def _send_invalid_payment_notification(wallet, error):
    """Send invalid payment method notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'auto_refill_invalid_payment',
            'title': 'Auto Refill Payment Method Invalid',
            'message': f'Your auto-refill payment method is invalid: {error}',
            'data': {
                'error': error,
                'payment_method': wallet.auto_refill_payment_method,
                'threshold': wallet.auto_refill_threshold,
                'amount': wallet.auto_refill_amount,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending invalid payment notification: {e}")


def _store_daily_refill_stats(date, stats):
    """Store daily refill statistics."""
    try:
        # This would implement actual storage of daily statistics
        # For example, save to a statistics table or cache
        logger.info(f"Storing daily refill stats for {date}: {stats}")
        
    except Exception as e:
        logger.error(f"Error storing daily refill stats: {e}")
