"""
Auto Refill Service

Service for managing automatic wallet refills,
including threshold monitoring and payment processing.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.billing import AdvertiserWallet, AdvertiserDeposit
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AutoRefillService:
    """
    Service for managing automatic wallet refills.
    
    Handles threshold monitoring, payment processing,
    and refill configuration.
    """
    
    def __init__(self):
        self.logger = logger
    
    def configure_auto_refill(self, advertiser, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure auto refill for advertiser wallet.
        
        Args:
            advertiser: Advertiser instance
            config: Auto refill configuration
            
        Returns:
            Dict[str, Any]: Configuration result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Get or create wallet
                wallet, created = AdvertiserWallet.objects.get_or_create(
                    advertiser=advertiser,
                    defaults={
                        'balance': 0.00,
                        'credit_limit': 0.00,
                        'available_credit': 0.00,
                        'currency': 'USD',
                    }
                )
                
                # Validate configuration
                self._validate_refill_config(config)
                
                # Update wallet auto refill settings
                wallet.auto_refill_enabled = config.get('enabled', False)
                wallet.auto_refill_threshold = config.get('threshold', 0.00)
                wallet.auto_refill_amount = config.get('amount', 0.00)
                wallet.auto_refill_max = config.get('max_amount')
                wallet.default_payment_method = config.get('payment_method', 'credit_card')
                wallet.save()
                
                # Store payment details in metadata
                metadata = wallet.metadata or {}
                metadata['auto_refill'] = {
                    'configured_at': timezone.now().isoformat(),
                    'payment_token': config.get('payment_token'),
                    'billing_address': config.get('billing_address'),
                    'last_refill_at': None,
                    'total_refills': 0,
                    'failed_attempts': 0,
                    'last_failure_reason': None,
                }
                wallet.metadata = metadata
                wallet.save()
                
                # Send notification
                if wallet.auto_refill_enabled:
                    self._send_auto_refill_enabled_notification(advertiser, wallet)
                
                self.logger.info(f"Configured auto refill for {advertiser.company_name}")
                
                return {
                    'success': True,
                    'wallet_id': wallet.id,
                    'enabled': wallet.auto_refill_enabled,
                    'threshold': float(wallet.auto_refill_threshold),
                    'amount': float(wallet.auto_refill_amount),
                    'max_amount': wallet.auto_refill_max,
                }
                
        except Exception as e:
            self.logger.error(f"Error configuring auto refill: {e}")
            raise ValidationError(f"Failed to configure auto refill: {str(e)}")
    
    def check_and_process_auto_refills(self) -> Dict[str, Any]:
        """
        Check and process auto refills for all enabled wallets.
        
        Returns:
            Dict[str, Any]: Processing results
        """
        try:
            now = timezone.now()
            
            # Get wallets with auto refill enabled
            wallets = AdvertiserWallet.objects.filter(
                auto_refill_enabled=True,
                is_active=True,
                is_suspended=False,
            ).select_related('advertiser')
            
            processed_count = 0
            successful_count = 0
            failed_count = 0
            skipped_count = 0
            errors = []
            
            for wallet in wallets:
                try:
                    if self._should_process_refill(wallet):
                        result = self._process_auto_refill(wallet)
                        
                        if result['success']:
                            successful_count += 1
                        else:
                            failed_count += 1
                            errors.append({
                                'wallet_id': wallet.id,
                                'advertiser': wallet.advertiser.company_name,
                                'error': result.get('error', 'Unknown error')
                            })
                        
                        processed_count += 1
                    else:
                        skipped_count += 1
                
                except Exception as e:
                    errors.append({
                        'wallet_id': wallet.id,
                        'advertiser': wallet.advertiser.company_name,
                        'error': str(e)
                    })
                    failed_count += 1
            
            return {
                'wallets_checked': wallets.count(),
                'processed_count': processed_count,
                'successful_count': successful_count,
                'failed_count': failed_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'timestamp': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error checking auto refills: {e}")
            raise ValidationError(f"Failed to check auto refills: {str(e)}")
    
    def process_manual_refill(self, advertiser, amount: float, payment_method: str, payment_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process manual refill for advertiser.
        
        Args:
            advertiser: Advertiser instance
            amount: Refill amount
            payment_method: Payment method
            payment_details: Payment details
            
        Returns:
            Dict[str, Any]: Processing result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate amount
                if amount <= 0:
                    raise ValidationError("Refill amount must be positive")
                
                # Get wallet
                try:
                    wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
                except AdvertiserWallet.DoesNotExist:
                    raise ValidationError("Advertiser wallet not found")
                
                # Process payment
                payment_result = self._process_payment(payment_method, amount, payment_details)
                
                if not payment_result['success']:
                    return {
                        'success': False,
                        'error': payment_result['error'],
                        'transaction_id': None,
                    }
                
                # Add funds to wallet
                wallet.add_funds(amount, f"Manual refill via {payment_method}")
                
                # Create deposit record
                deposit = AdvertiserDeposit.objects.create(
                    advertiser=advertiser,
                    amount=amount,
                    currency='USD',
                    gateway=payment_method,
                    payment_method=payment_method,
                    gateway_transaction_id=payment_result['transaction_id'],
                    status='completed',
                    processing_fee=payment_result.get('processing_fee', 0.00),
                    net_amount=amount - payment_result.get('processing_fee', 0.00),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    completed_at=timezone.now(),
                )
                
                # Send notification
                self._send_manual_refill_notification(advertiser, deposit)
                
                self.logger.info(f"Processed manual refill: ${amount:.2f} for {advertiser.company_name}")
                
                return {
                    'success': True,
                    'deposit_id': deposit.id,
                    'transaction_id': payment_result['transaction_id'],
                    'amount': float(amount),
                    'new_balance': float(wallet.balance),
                }
                
        except Exception as e:
            self.logger.error(f"Error processing manual refill: {e}")
            raise ValidationError(f"Failed to process manual refill: {str(e)}")
    
    def get_auto_refill_status(self, advertiser) -> Dict[str, Any]:
        """
        Get auto refill status for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Auto refill status
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            try:
                wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            except AdvertiserWallet.DoesNotExist:
                return {
                    'has_wallet': False,
                    'auto_refill_enabled': False,
                }
            
            metadata = wallet.metadata or {}
            refill_metadata = metadata.get('auto_refill', {})
            
            return {
                'has_wallet': True,
                'auto_refill_enabled': wallet.auto_refill_enabled,
                'threshold': float(wallet.auto_refill_threshold),
                'amount': float(wallet.auto_refill_amount),
                'max_amount': wallet.auto_refill_max,
                'payment_method': wallet.default_payment_method,
                'current_balance': float(wallet.balance),
                'is_below_threshold': wallet.balance <= wallet.auto_refill_threshold,
                'can_refill': self._can_refill(wallet),
                'statistics': {
                    'last_refill_at': refill_metadata.get('last_refill_at'),
                    'total_refills': refill_metadata.get('total_refills', 0),
                    'failed_attempts': refill_metadata.get('failed_attempts', 0),
                    'last_failure_reason': refill_metadata.get('last_failure_reason'),
                    'configured_at': refill_metadata.get('configured_at'),
                },
                'next_refill_estimate': self._estimate_next_refill(wallet),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting auto refill status: {e}")
            raise ValidationError(f"Failed to get auto refill status: {str(e)}")
    
    def disable_auto_refill(self, advertiser) -> Dict[str, Any]:
        """
        Disable auto refill for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Disable result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Get wallet
                try:
                    wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
                except AdvertiserWallet.DoesNotExist:
                    raise ValidationError("Advertiser wallet not found")
                
                # Disable auto refill
                wallet.auto_refill_enabled = False
                wallet.save()
                
                # Clear payment token from metadata
                metadata = wallet.metadata or {}
                if 'auto_refill' in metadata:
                    metadata['auto_refill']['payment_token'] = None
                    metadata['auto_refill']['disabled_at'] = timezone.now().isoformat()
                    wallet.metadata = metadata
                    wallet.save()
                
                # Send notification
                self._send_auto_refill_disabled_notification(advertiser, wallet)
                
                self.logger.info(f"Disabled auto refill for {advertiser.company_name}")
                
                return {
                    'success': True,
                    'disabled_at': timezone.now().isoformat(),
                }
                
        except Exception as e:
            self.logger.error(f"Error disabling auto refill: {e}")
            raise ValidationError(f"Failed to disable auto refill: {str(e)}")
    
    def get_refill_history(self, advertiser, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get refill history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            limit: Maximum number of records
            
        Returns:
            List[Dict[str, Any]]: Refill history
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            deposits = AdvertiserDeposit.objects.filter(
                advertiser=advertiser,
                status='completed'
            ).order_by('-completed_at')[:limit]
            
            history = []
            for deposit in deposits:
                history.append({
                    'id': deposit.id,
                    'amount': float(deposit.amount),
                    'net_amount': float(deposit.net_amount),
                    'processing_fee': float(deposit.processing_fee),
                    'gateway': deposit.gateway,
                    'payment_method': deposit.payment_method,
                    'completed_at': deposit.completed_at.isoformat(),
                    'is_auto_refill': deposit.gateway in ['auto_refill_credit_card', 'auto_refill_paypal'],
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting refill history: {e}")
            raise ValidationError(f"Failed to get refill history: {str(e)}")
    
    def _validate_refill_config(self, config: Dict[str, Any]):
        """Validate refill configuration."""
        if config.get('enabled', False):
            threshold = config.get('threshold', 0)
            amount = config.get('amount', 0)
            
            if threshold <= 0:
                raise ValidationError("Auto refill threshold must be positive")
            
            if amount <= 0:
                raise ValidationError("Auto refill amount must be positive")
            
            if amount < threshold:
                raise ValidationError("Auto refill amount must be greater than threshold")
            
            max_amount = config.get('max_amount')
            if max_amount is not None and max_amount <= 0:
                raise ValidationError("Maximum auto refill amount must be positive")
    
    def _should_process_refill(self, wallet: AdvertiserWallet) -> bool:
        """Check if auto refill should be processed."""
        if not wallet.auto_refill_enabled:
            return False
        
        if wallet.balance > wallet.auto_refill_threshold:
            return False
        
        if not self._can_refill(wallet):
            return False
        
        return True
    
    def _can_refill(self, wallet: AdvertiserWallet) -> bool:
        """Check if wallet can be refilled."""
        metadata = wallet.metadata or {}
        refill_metadata = metadata.get('auto_refill', {})
        
        # Check max amount limit
        if wallet.auto_refill_max:
            total_refills = refill_metadata.get('total_refills', 0)
            if total_refills >= wallet.auto_refill_max:
                return False
        
        # Check failed attempts
        failed_attempts = refill_metadata.get('failed_attempts', 0)
        if failed_attempts >= 3:  # Max 3 failed attempts
            return False
        
        # Check last failure time
        last_failure_reason = refill_metadata.get('last_failure_reason')
        if last_failure_reason:
            # Would implement cooldown period logic
            pass
        
        return True
    
    def _process_auto_refill(self, wallet: AdvertiserWallet) -> Dict[str, Any]:
        """Process auto refill for wallet."""
        try:
            metadata = wallet.metadata or {}
            refill_metadata = metadata.get('auto_refill', {})
            
            # Get payment details
            payment_method = wallet.default_payment_method
            payment_token = refill_metadata.get('payment_token')
            billing_address = refill_metadata.get('billing_address')
            
            if not payment_token:
                return {
                    'success': False,
                    'error': 'No payment token available',
                }
            
            payment_details = {
                'token': payment_token,
                'billing_address': billing_address,
            }
            
            # Process payment
            payment_result = self._process_payment(payment_method, wallet.auto_refill_amount, payment_details)
            
            if not payment_result['success']:
                # Update failure count
                refill_metadata['failed_attempts'] += 1
                refill_metadata['last_failure_reason'] = payment_result['error']
                wallet.metadata = metadata
                wallet.save()
                
                return {
                    'success': False,
                    'error': payment_result['error'],
                }
            
            # Add funds to wallet
            wallet.add_funds(wallet.auto_refill_amount, f"Auto refill via {payment_method}")
            
            # Create deposit record
            deposit = AdvertiserDeposit.objects.create(
                advertiser=wallet.advertiser,
                amount=wallet.auto_refill_amount,
                currency='USD',
                gateway=f'auto_refill_{payment_method}',
                payment_method=payment_method,
                gateway_transaction_id=payment_result['transaction_id'],
                status='completed',
                processing_fee=payment_result.get('processing_fee', 0.00),
                net_amount=wallet.auto_refill_amount - payment_result.get('processing_fee', 0.00),
                created_at=timezone.now(),
                updated_at=timezone.now(),
                completed_at=timezone.now(),
            )
            
            # Update refill metadata
            refill_metadata['last_refill_at'] = timezone.now().isoformat()
            refill_metadata['total_refills'] += 1
            refill_metadata['failed_attempts'] = 0
            refill_metadata['last_failure_reason'] = None
            wallet.metadata = metadata
            wallet.save()
            
            # Send notification
            self._send_auto_refill_notification(wallet.advertiser, deposit)
            
            self.logger.info(f"Processed auto refill: ${wallet.auto_refill_amount:.2f} for {wallet.advertiser.company_name}")
            
            return {
                'success': True,
                'deposit_id': deposit.id,
                'amount': float(wallet.auto_refill_amount),
                'new_balance': float(wallet.balance),
            }
            
        except Exception as e:
            self.logger.error(f"Error processing auto refill: {e}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def _process_payment(self, payment_method: str, amount: float, payment_details: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment (placeholder implementation)."""
        # This would implement actual payment processing
        # For now, return success
        
        import uuid
        transaction_id = str(uuid.uuid4())
        
        # Calculate processing fee
        processing_fee = self._calculate_processing_fee(amount, payment_method)
        
        return {
            'success': True,
            'transaction_id': transaction_id,
            'processing_fee': processing_fee,
            'amount': amount,
        }
    
    def _calculate_processing_fee(self, amount: float, payment_method: str) -> float:
        """Calculate processing fee."""
        if payment_method == 'credit_card':
            return amount * 0.029 + 0.30
        elif payment_method == 'paypal':
            return amount * 0.034 + 0.30
        else:
            return 0.00
    
    def _estimate_next_refill(self, wallet: AdvertiserWallet) -> Optional[str]:
        """Estimate when next refill might occur."""
        if not wallet.auto_refill_enabled:
            return None
        
        if wallet.balance > wallet.auto_refill_threshold:
            # Would estimate based on spend rate
            return "Unknown - balance above threshold"
        
        return "Immediate - balance below threshold"
    
    def _send_auto_refill_enabled_notification(self, advertiser, wallet: AdvertiserWallet):
        """Send auto refill enabled notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='payment_received',
            title=_('Auto Refill Enabled'),
            message=_(
                'Auto refill has been enabled for your account. '
                'Your wallet will be automatically refilled when balance drops below ${threshold:.2f}.'
            ).format(threshold=float(wallet.auto_refill_threshold)),
            priority='medium',
            action_url='/advertiser/billing/auto-refill/',
            action_text=_('Manage Settings')
        )
    
    def _send_auto_refill_disabled_notification(self, advertiser, wallet: AdvertiserWallet):
        """Send auto refill disabled notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='payment_received',
            title=_('Auto Refill Disabled'),
            message=_('Auto refill has been disabled for your account.'),
            priority='medium',
            action_url='/advertiser/billing/auto-refill/',
            action_text=_('Manage Settings')
        )
    
    def _send_auto_refill_notification(self, advertiser, deposit: AdvertiserDeposit):
        """Send auto refill notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='payment_received',
            title=_('Auto Refill Processed'),
            message=_(
                'Your wallet has been automatically refilled with ${amount:.2f}. '
                'Available balance: ${balance:.2f}'
            ).format(
                amount=float(deposit.net_amount),
                balance=float(self._get_wallet_balance(advertiser)['available_balance'])
            ),
            priority='medium',
            action_url='/advertiser/billing/transactions/',
            action_text=_('View Transactions')
        )
    
    def _send_manual_refill_notification(self, advertiser, deposit: AdvertiserDeposit):
        """Send manual refill notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='payment_received',
            title=_('Wallet Refilled'),
            message=_(
                'Your wallet has been refilled with ${amount:.2f}. '
                'Available balance: ${balance:.2f}'
            ).format(
                amount=float(deposit.net_amount),
                balance=float(self._get_wallet_balance(advertiser)['available_balance'])
            ),
            priority='medium',
            action_url='/advertiser/billing/transactions/',
            action_text=_('View Transactions')
        )
    
    def _get_wallet_balance(self, advertiser) -> Dict[str, Any]:
        """Get wallet balance (simplified version)."""
        try:
            wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            return {
                'available_balance': float(wallet.available_balance),
            }
        except AdvertiserWallet.DoesNotExist:
            return {
                'available_balance': 0.00,
            }
