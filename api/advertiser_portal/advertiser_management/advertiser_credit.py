"""
Advertiser Credit Management

This module handles credit management for advertisers including credit limits,
balance tracking, credit adjustments, and credit history.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser, AdvertiserCredit
from ..database_models.billing_model import BillingProfile
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserCreditService:
    """Service for managing advertiser credit operations."""
    
    @staticmethod
    def allocate_credit(advertiser_id: UUID, credit_data: Dict[str, Any],
                        allocated_by: Optional[User] = None) -> AdvertiserCredit:
        """Allocate credit to advertiser."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            # Validate credit data
            amount = Decimal(str(credit_data.get('amount', 0)))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            credit_type = credit_data.get('credit_type', 'allocation')
            if credit_type not in ['allocation', 'bonus', 'refund', 'adjustment']:
                raise AdvertiserValidationError("Invalid credit type")
            
            with transaction.atomic():
                # Create credit record
                credit_record = AdvertiserCredit.objects.create(
                    advertiser=advertiser,
                    credit_type=credit_type,
                    amount=amount,
                    description=credit_data.get('description', f'{credit_type.title()} credit allocation'),
                    reference_number=credit_data.get('reference_number', ''),
                    expires_at=credit_data.get('expires_at'),
                    created_by=allocated_by
                )
                
                # Update billing profile credit available
                billing_profile.credit_available += amount
                billing_profile.save(update_fields=['credit_available'])
                
                # Update credit record with new balance
                credit_record.balance_after = billing_profile.credit_available
                credit_record.save(update_fields=['balance_after'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=allocated_by,
                    title='Credit Allocated',
                    message=f'{credit_type.title()} credit of {billing_profile.default_currency} {amount} has been allocated to your account.',
                    notification_type='credit',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log allocation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='allocate_credit',
                    object_type='AdvertiserCredit',
                    object_id=str(credit_record.id),
                    user=allocated_by,
                    advertiser=advertiser,
                    description=f"Allocated {credit_type} credit: {amount}"
                )
                
                return credit_record
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error allocating credit {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to allocate credit: {str(e)}")
    
    @staticmethod
    def spend_credit(advertiser_id: UUID, spend_data: Dict[str, Any],
                      spent_by: Optional[User] = None) -> bool:
        """Spend credit from advertiser account."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            # Validate spend data
            amount = Decimal(str(spend_data.get('amount', 0)))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            # Check sufficient credit
            if billing_profile.credit_available < amount:
                raise AdvertiserValidationError("Insufficient credit available")
            
            with transaction.atomic():
                # Create credit record
                credit_record = AdvertiserCredit.objects.create(
                    advertiser=advertiser,
                    credit_type='spend',
                    amount=-amount,  # Negative for spending
                    description=spend_data.get('description', 'Credit spend'),
                    reference_number=spend_data.get('reference_number', ''),
                    campaign_id=spend_data.get('campaign_id'),
                    created_by=spent_by
                )
                
                # Update billing profile
                billing_profile.credit_available -= amount
                billing_profile.save(update_fields=['credit_available'])
                
                # Update advertiser total spend
                advertiser.total_spend += amount
                advertiser.save(update_fields=['total_spend'])
                
                # Update credit record with new balance
                credit_record.balance_after = billing_profile.credit_available
                credit_record.save(update_fields=['balance_after'])
                
                # Check for low credit alerts
                if billing_profile.credit_available < billing_profile.credit_limit * 0.2:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Low Credit Warning',
                        message=f'Your available credit is low: {billing_profile.credit_available}.',
                        notification_type='credit',
                        priority='medium',
                        channels=['in_app']
                    )
                
                # Log spend
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='spend_credit',
                    object_type='AdvertiserCredit',
                    object_id=str(credit_record.id),
                    user=spent_by,
                    advertiser=advertiser,
                    description=f"Spent credit: {amount}"
                )
                
                return True
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error spending credit {advertiser_id}: {str(e)}")
            return False
    
    @staticmethod
    def adjust_credit(advertiser_id: UUID, adjustment_data: Dict[str, Any],
                       adjusted_by: Optional[User] = None) -> bool:
        """Adjust credit balance for advertiser."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            # Validate adjustment data
            amount = Decimal(str(adjustment_data.get('amount', 0)))
            if amount == 0:
                raise AdvertiserValidationError("amount cannot be zero")
            
            adjustment_type = adjustment_data.get('adjustment_type', 'manual')
            if adjustment_type not in ['manual', 'bonus', 'penalty', 'refund', 'correction']:
                raise AdvertiserValidationError("Invalid adjustment type")
            
            with transaction.atomic():
                # Create credit record
                credit_record = AdvertiserCredit.objects.create(
                    advertiser=advertiser,
                    credit_type='adjustment',
                    amount=amount,
                    description=adjustment_data.get('description', f'{adjustment_type.title()} credit adjustment'),
                    reference_number=adjustment_data.get('reference_number', ''),
                    created_by=adjusted_by
                )
                
                # Update billing profile
                billing_profile.credit_available += amount
                billing_profile.save(update_fields=['credit_available'])
                
                # Update credit record with new balance
                credit_record.balance_after = billing_profile.credit_available
                credit_record.save(update_fields=['balance_after'])
                
                # Send notification for significant adjustments
                if abs(amount) >= 100:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=adjusted_by,
                        title='Credit Adjustment',
                        message=f'Your credit has been adjusted by {billing_profile.default_currency} {amount}.',
                        notification_type='credit',
                        priority='high',
                        channels=['in_app']
                    )
                
                # Log adjustment
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='adjust_credit',
                    object_type='AdvertiserCredit',
                    object_id=str(credit_record.id),
                    user=adjusted_by,
                    advertiser=advertiser,
                    description=f"Adjusted credit: {amount}"
                )
                
                return True
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error adjusting credit {advertiser_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_credit_balance(advertiser_id: UUID) -> Dict[str, Any]:
        """Get credit balance information."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            # Get credit summary
            total_allocated = AdvertiserCredit.objects.filter(
                advertiser=advertiser,
                credit_type__in=['allocation', 'bonus', 'refund']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_spent = AdvertiserCredit.objects.filter(
                advertiser=advertiser,
                credit_type='spend'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_adjustments = AdvertiserCredit.objects.filter(
                advertiser=advertiser,
                credit_type='adjustment'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get credit by type
            credit_by_type = AdvertiserCredit.objects.filter(advertiser=advertiser).values('credit_type').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            
            # Calculate utilization
            utilization = ((billing_profile.credit_limit - billing_profile.credit_available) / billing_profile.credit_limit * 100) if billing_profile.credit_limit > 0 else 0
            
            return {
                'advertiser_id': str(advertiser_id),
                'credit_balance': {
                    'credit_limit': float(billing_profile.credit_limit),
                    'credit_available': float(billing_profile.credit_available),
                    'credit_utilization': utilization,
                    'account_balance': float(advertiser.account_balance)
                },
                'credit_summary': {
                    'total_allocated': float(total_allocated),
                    'total_spent': float(abs(total_spent)),
                    'total_adjustments': float(total_adjustments),
                    'net_balance': float(billing_profile.credit_available)
                },
                'credit_by_type': [
                    {
                        'credit_type': item['credit_type'],
                        'total_amount': float(item['total_amount']),
                        'count': item['count']
                    }
                    for item in credit_by_type
                ],
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting credit balance {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get credit balance: {str(e)}")
    
    @staticmethod
    def get_credit_history(advertiser_id: UUID, filters: Optional[Dict[str, Any]] = None,
                           page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get credit history for advertiser."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            
            queryset = AdvertiserCredit.objects.filter(advertiser=advertiser)
            
            # Apply filters
            if filters:
                if 'credit_type' in filters:
                    queryset = queryset.filter(credit_type=filters['credit_type'])
                if 'date_from' in filters:
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
                if 'amount_min' in filters:
                    queryset = queryset.filter(amount__gte=filters['amount_min'])
                if 'amount_max' in filters:
                    queryset = queryset.filter(amount__lte=filters['amount_max'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(description__icontains=search) |
                        Q(reference_number__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            credit_records = queryset[offset:offset + page_size].order_by('-created_at')
            
            return {
                'advertiser_id': str(advertiser_id),
                'credit_history': [
                    {
                        'id': str(record.id),
                        'credit_type': record.credit_type,
                        'amount': float(record.amount),
                        'description': record.description,
                        'reference_number': record.reference_number,
                        'balance_after': float(record.balance_after),
                        'campaign_id': str(record.campaign_id) if record.campaign_id else None,
                        'expires_at': record.expires_at.isoformat() if record.expires_at else None,
                        'created_at': record.created_at.isoformat()
                    }
                    for record in credit_records
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting credit history {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get credit history: {str(e)}")
    
    @staticmethod
    def get_credit_usage_report(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get credit usage report."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get credit records in date range
            credit_records = AdvertiserCredit.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Aggregate by credit type
            credit_by_type = credit_records.values('credit_type').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            
            # Aggregate by date
            credit_by_date = credit_records.extra(
                {'date': 'date(created_at)'}
            ).values('date').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            ).order_by('date')
            
            # Calculate totals
            total_allocated = credit_records.filter(
                credit_type__in=['allocation', 'bonus', 'refund']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_spent = credit_records.filter(
                credit_type='spend'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_adjustments = credit_records.filter(
                credit_type='adjustment'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get daily usage trend
            daily_usage = []
            for record in credit_by_date:
                daily_usage.append({
                    'date': record['date'].isoformat(),
                    'total_amount': float(record['total_amount']),
                    'transaction_count': record['count']
                })
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'summary': {
                    'total_allocated': float(total_allocated),
                    'total_spent': float(abs(total_spent)),
                    'total_adjustments': float(total_adjustments),
                    'net_change': float(total_allocated + total_spent + total_adjustments),
                    'transaction_count': credit_records.count()
                },
                'credit_by_type': [
                    {
                        'credit_type': item['credit_type'],
                        'total_amount': float(item['total_amount']),
                        'count': item['count']
                    }
                    for item in credit_by_type
                ],
                'daily_usage': daily_usage,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting credit usage report {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get credit usage report: {str(e)}")
    
    @staticmethod
    def check_credit_limit(advertiser_id: UUID, amount: Decimal) -> Dict[str, Any]:
        """Check if advertiser has sufficient credit for amount."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            # Check credit limit
            available_credit = billing_profile.credit_available
            credit_limit = billing_profile.credit_limit
            
            # Check if amount exceeds available credit
            if amount > available_credit:
                return {
                    'sufficient': False,
                    'available_credit': float(available_credit),
                    'requested_amount': float(amount),
                    'shortfall': float(amount - available_credit),
                    'message': 'Insufficient credit available'
                }
            
            # Check if amount exceeds credit limit
            if amount > credit_limit:
                return {
                    'sufficient': False,
                    'available_credit': float(available_credit),
                    'requested_amount': float(amount),
                    'limit_exceeded': True,
                    'message': 'Amount exceeds credit limit'
                }
            
            # Check utilization threshold
            utilization = ((credit_limit - available_credit) / credit_limit * 100) if credit_limit > 0 else 0
            high_utilization = utilization > 80
            
            return {
                'sufficient': True,
                'available_credit': float(available_credit),
                'requested_amount': float(amount),
                'remaining_after': float(available_credit - amount),
                'utilization': utilization,
                'high_utilization': high_utilization,
                'message': 'Sufficient credit available'
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error checking credit limit {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to check credit limit: {str(e)}")
    
    @staticmethod
    def set_credit_limit(advertiser_id: UUID, new_limit: Decimal, reason: str = '',
                         set_by: Optional[User] = None) -> bool:
        """Set credit limit for advertiser."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            if new_limit < 0:
                raise AdvertiserValidationError("Credit limit cannot be negative")
            
            with transaction.atomic():
                old_limit = billing_profile.credit_limit
                
                # Update credit limit
                billing_profile.credit_limit = new_limit
                billing_profile.save(update_fields=['credit_limit'])
                
                # Create adjustment record if limit increased
                if new_limit > old_limit:
                    increase_amount = new_limit - old_limit
                    AdvertiserCredit.objects.create(
                        advertiser=advertiser,
                        credit_type='adjustment',
                        amount=increase_amount,
                        description=f'Credit limit increased from {old_limit} to {new_limit}. {reason}',
                        reference_number=f'LIMIT_ADJUST_{timezone.now().strftime("%Y%m%d")}',
                        created_by=set_by
                    )
                    
                    # Update credit available
                    billing_profile.credit_available += increase_amount
                    billing_profile.save(update_fields=['credit_available'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=set_by,
                    title='Credit Limit Updated',
                    message=f'Your credit limit has been {("increased" if new_limit > old_limit else "decreased")} to {billing_profile.default_currency} {new_limit}.',
                    notification_type='credit',
                    priority='high',
                    channels=['in_app']
                )
                
                # Log change
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='set_credit_limit',
                    object_type='BillingProfile',
                    object_id=str(billing_profile.id),
                    user=set_by,
                    advertiser=advertiser,
                    description=f"Updated credit limit: {old_limit} -> {new_limit}"
                )
                
                return True
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error setting credit limit {advertiser_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_credit_alerts(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get credit alerts for advertiser."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = AdvertiserCreditService.get_billing_profile(advertiser_id)
            
            alerts = []
            
            # Check low credit alert
            if billing_profile.credit_available < billing_profile.credit_limit * 0.2:
                alerts.append({
                    'type': 'low_credit',
                    'severity': 'high',
                    'message': f'Credit balance is low: {billing_profile.credit_available}',
                    'threshold': 20,
                    'current_value': billing_profile.credit_available,
                    'recommended_action': 'Add more credit to avoid campaign interruptions'
                })
            
            # Check credit utilization alert
            utilization = ((billing_profile.credit_limit - billing_profile.credit_available) / billing_profile.credit_limit * 100) if billing_profile.credit_limit > 0 else 0
            if utilization > 80:
                alerts.append({
                    'type': 'high_utilization',
                    'severity': 'medium',
                    'message': f'Credit utilization is high: {utilization:.1f}%',
                    'threshold': 80,
                    'current_value': utilization,
                    'recommended_action': 'Monitor spending and consider increasing credit limit'
                })
            
            # Check negative balance alert
            if billing_profile.credit_available < 0:
                alerts.append({
                    'type': 'negative_balance',
                    'severity': 'critical',
                    'message': f'Credit balance is negative: {billing_profile.credit_available}',
                    'threshold': 0,
                    'current_value': billing_profile.credit_available,
                    'recommended_action': 'Add credit immediately to restore account balance'
                })
            
            # Check expiring credit
            expiring_soon = AdvertiserCredit.objects.filter(
                advertiser=advertiser,
                credit_type__in=['allocation', 'bonus'],
                expires_at__lte=timezone.now() + timezone.timedelta(days=7),
                expires_at__gt=timezone.now()
            )
            
            if expiring_soon.exists():
                alerts.append({
                    'type': 'expiring_credit',
                    'severity': 'medium',
                    'message': f'{expiring_soon.count()} credit allocation(s) expiring soon',
                    'threshold': 7,
                    'current_value': expiring_soon.count(),
                    'recommended_action': 'Use credit before expiration or request extension'
                })
            
            return alerts
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting credit alerts {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_billing_profile(advertiser_id: UUID) -> BillingProfile:
        """Get billing profile for advertiser."""
        try:
            advertiser = AdvertiserCreditService.get_advertiser(advertiser_id)
            billing_profile = BillingProfile.objects.filter(advertiser=advertiser).first()
            
            if not billing_profile:
                raise AdvertiserNotFoundError(f"Billing profile not found for advertiser {advertiser_id}")
            
            return billing_profile
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting billing profile {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get billing profile: {str(e)}")
    
    @staticmethod
    def get_credit_statistics() -> Dict[str, Any]:
        """Get credit statistics across all advertisers."""
        try:
            # Get total credit statistics
            total_credit_limit = BillingProfile.objects.aggregate(
                total=Sum('credit_limit')
            )['total'] or Decimal('0.00')
            
            total_credit_available = BillingProfile.objects.aggregate(
                total=Sum('credit_available')
            )['total'] or Decimal('0.00')
            
            total_credit_used = total_credit_limit - total_credit_available
            
            # Get credit records statistics
            total_allocated = AdvertiserCredit.objects.filter(
                credit_type__in=['allocation', 'bonus', 'refund']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            total_spent = AdvertiserCredit.objects.filter(
                credit_type='spend'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get credit by type
            credit_by_type = AdvertiserCredit.objects.values('credit_type').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            
            # Get low credit advertisers
            low_credit_advertisers = BillingProfile.objects.filter(
                credit_available__lt=F('credit_limit') * 0.2
            ).count()
            
            # Get overdrawn advertisers
            overdrawn_advertisers = BillingProfile.objects.filter(
                credit_available__lt=0
            ).count()
            
            return {
                'total_credit_limit': float(total_credit_limit),
                'total_credit_available': float(total_credit_available),
                'total_credit_used': float(total_credit_used),
                'credit_utilization': float((total_credit_used / total_credit_limit * 100) if total_credit_limit > 0 else 0),
                'total_allocated': float(total_allocated),
                'total_spent': float(abs(total_spent)),
                'low_credit_advertisers': low_credit_advertisers,
                'overdrawn_advertisers': overdrawn_advertisers,
                'credit_by_type': list(credit_by_type)
            }
            
        except Exception as e:
            logger.error(f"Error getting credit statistics: {str(e)}")
            return {
                'total_credit_limit': 0,
                'total_credit_available': 0,
                'total_credit_used': 0,
                'credit_utilization': 0,
                'total_allocated': 0,
                'total_spent': 0,
                'low_credit_advertisers': 0,
                'overdrawn_advertisers': 0,
                'credit_by_type': []
            }
