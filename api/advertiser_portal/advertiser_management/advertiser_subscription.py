"""
Advertiser Subscription Management

This module handles subscription plans, billing cycles, subscription management,
and subscription-related operations for advertisers.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.subscription_model import Subscription, SubscriptionPlan, SubscriptionUsage, SubscriptionInvoice
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserSubscriptionService:
    """Service for managing advertiser subscription operations."""
    
    @staticmethod
    def create_subscription(advertiser_id: UUID, subscription_data: Dict[str, Any],
                            created_by: Optional[User] = None) -> Subscription:
        """Create subscription for advertiser."""
        try:
            advertiser = AdvertiserSubscriptionService.get_advertiser(advertiser_id)
            
            # Validate subscription data
            plan_id = subscription_data.get('plan_id')
            if not plan_id:
                raise AdvertiserValidationError("plan_id is required")
            
            subscription_plan = AdvertiserSubscriptionService.get_subscription_plan(plan_id)
            
            # Check if advertiser already has active subscription
            existing_subscription = Subscription.objects.filter(
                advertiser=advertiser,
                status='active'
            ).first()
            
            if existing_subscription:
                raise AdvertiserValidationError(f"Advertiser already has active subscription: {existing_subscription.id}")
            
            with transaction.atomic():
                # Calculate subscription dates
                start_date = subscription_data.get('start_date', date.today())
                end_date = AdvertiserSubscriptionService._calculate_subscription_end_date(
                    start_date, subscription_plan.billing_cycle
                )
                
                # Create subscription
                subscription = Subscription.objects.create(
                    advertiser=advertiser,
                    plan=subscription_plan,
                    status='active',
                    start_date=start_date,
                    end_date=end_date,
                    billing_cycle=subscription_plan.billing_cycle,
                    price=subscription_plan.price,
                    currency=subscription_plan.currency,
                    auto_renew=subscription_data.get('auto_renew', True),
                    payment_method_id=subscription_data.get('payment_method_id'),
                    usage_limits=subscription_plan.features,
                    current_usage={},
                    trial_end_date=subscription_data.get('trial_end_date'),
                    created_by=created_by
                )
                
                # Create initial usage record
                SubscriptionUsage.objects.create(
                    subscription=subscription,
                    usage_type='subscription_created',
                    usage_amount=1,
                    description='Subscription created',
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Subscription Created',
                    message=f'Your {subscription_plan.name} subscription has been activated.',
                    notification_type='subscription',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    subscription,
                    created_by,
                    description=f"Created subscription: {subscription_plan.name}"
                )
                
                return subscription
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except SubscriptionPlan.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription plan {plan_id} not found")
        except Exception as e:
            logger.error(f"Error creating subscription {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create subscription: {str(e)}")
    
    @staticmethod
    def upgrade_subscription(subscription_id: UUID, new_plan_id: UUID,
                            upgraded_by: Optional[User] = None) -> Subscription:
        """Upgrade subscription to new plan."""
        try:
            subscription = AdvertiserSubscriptionService.get_subscription(subscription_id)
            new_plan = AdvertiserSubscriptionService.get_subscription_plan(new_plan_id)
            
            if subscription.status != 'active':
                raise AdvertiserValidationError(f"Cannot upgrade subscription in status: {subscription.status}")
            
            if new_plan.price <= subscription.plan.price:
                raise AdvertiserValidationError("New plan must be more expensive than current plan")
            
            with transaction.atomic():
                # Calculate proration
                old_plan = subscription.plan
                remaining_days = (subscription.end_date - date.today()).days
                proration_amount = AdvertiserSubscriptionService._calculate_proration(
                    old_plan, new_plan, remaining_days
                )
                
                # Update subscription
                old_plan_id = subscription.plan.id
                subscription.plan = new_plan
                subscription.price = new_plan.price
                subscription.usage_limits = new_plan.features
                subscription.upgraded_at = timezone.now()
                subscription.previous_plan_id = old_plan_id
                subscription.save(update_fields=['plan', 'price', 'usage_limits', 'upgraded_at', 'previous_plan_id'])
                
                # Create usage record
                SubscriptionUsage.objects.create(
                    subscription=subscription,
                    usage_type='plan_upgrade',
                    usage_amount=float(new_plan.price - old_plan.price),
                    description=f'Upgraded from {old_plan.name} to {new_plan.name}',
                    metadata={
                        'proration_amount': float(proration_amount),
                        'remaining_days': remaining_days
                    },
                    created_by=upgraded_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=subscription.advertiser,
                    user=upgraded_by,
                    title='Subscription Upgraded',
                    message=f'Your subscription has been upgraded to {new_plan.name}.',
                    notification_type='subscription',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log upgrade
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='upgrade_subscription',
                    object_type='Subscription',
                    object_id=str(subscription.id),
                    user=upgraded_by,
                    advertiser=subscription.advertiser,
                    description=f"Upgraded subscription: {old_plan.name} -> {new_plan.name}"
                )
                
                return subscription
                
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
        except SubscriptionPlan.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription plan {new_plan_id} not found")
        except Exception as e:
            logger.error(f"Error upgrading subscription {subscription_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to upgrade subscription: {str(e)}")
    
    @staticmethod
    def downgrade_subscription(subscription_id: UUID, new_plan_id: UUID,
                              downgraded_by: Optional[User] = None) -> Subscription:
        """Downgrade subscription to new plan."""
        try:
            subscription = AdvertiserSubscriptionService.get_subscription(subscription_id)
            new_plan = AdvertiserSubscriptionService.get_subscription_plan(new_plan_id)
            
            if subscription.status != 'active':
                raise AdvertiserValidationError(f"Cannot downgrade subscription in status: {subscription.status}")
            
            if new_plan.price >= subscription.plan.price:
                raise AdvertiserValidationError("New plan must be less expensive than current plan")
            
            with transaction.atomic():
                # Schedule downgrade for next billing cycle
                old_plan = subscription.plan
                subscription.pending_plan_id = new_plan.id
                subscription.downgrade_scheduled_at = timezone.now()
                subscription.save(update_fields=['pending_plan_id', 'downgrade_scheduled_at'])
                
                # Create usage record
                SubscriptionUsage.objects.create(
                    subscription=subscription,
                    usage_type='plan_downgrade_scheduled',
                    usage_amount=float(old_plan.price - new_plan.price),
                    description=f'Downgrade scheduled: {old_plan.name} -> {new_plan.name}',
                    effective_date=subscription.end_date.isoformat(),
                    created_by=downgraded_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=subscription.advertiser,
                    user=downgraded_by,
                    title='Subscription Downgrade Scheduled',
                    message=f'Your subscription will be downgraded to {new_plan.name} on {subscription.end_date}.',
                    notification_type='subscription',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log downgrade
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='downgrade_subscription',
                    object_type='Subscription',
                    object_id=str(subscription.id),
                    user=downgraded_by,
                    advertiser=subscription.advertiser,
                    description=f"Scheduled downgrade: {old_plan.name} -> {new_plan.name}"
                )
                
                return subscription
                
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
        except SubscriptionPlan.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription plan {new_plan_id} not found")
        except Exception as e:
            logger.error(f"Error downgrading subscription {subscription_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to downgrade subscription: {str(e)}")
    
    @staticmethod
    def cancel_subscription(subscription_id: UUID, cancellation_data: Dict[str, Any],
                            cancelled_by: Optional[User] = None) -> bool:
        """Cancel subscription."""
        try:
            subscription = AdvertiserSubscriptionService.get_subscription(subscription_id)
            
            if subscription.status == 'cancelled':
                raise AdvertiserValidationError("Subscription is already cancelled")
            
            with transaction.atomic():
                # Update subscription status
                subscription.status = 'cancelled'
                subscription.cancelled_at = timezone.now()
                subscription.cancellation_reason = cancellation_data.get('reason', '')
                cancellation_effective_date = date.fromisoformat(cancellation_data.get('effective_date', date.today().isoformat()))
                subscription.cancellation_effective_date = cancellation_effective_date
                subscription.auto_renew = False
                subscription.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'cancellation_effective_date', 'auto_renew'])
                
                # Create usage record
                SubscriptionUsage.objects.create(
                    subscription=subscription,
                    usage_type='subscription_cancelled',
                    usage_amount=0,
                    description=f'Subscription cancelled: {cancellation_data.get("reason", "")}',
                    metadata={
                        'effective_date': cancellation_effective_date.isoformat()
                    },
                    created_by=cancelled_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=subscription.advertiser,
                    user=cancelled_by,
                    title='Subscription Cancelled',
                    message=f'Your subscription has been cancelled. Service will end on {cancellation_effective_date}.',
                    notification_type='subscription',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log cancellation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='cancel_subscription',
                    object_type='Subscription',
                    object_id=str(subscription.id),
                    user=cancelled_by,
                    advertiser=subscription.advertiser,
                    description=f"Cancelled subscription: {subscription.plan.name}"
                )
                
                return True
                
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
        except Exception as e:
            logger.error(f"Error cancelling subscription {subscription_id}: {str(e)}")
            return False
    
    @staticmethod
    def renew_subscription(subscription_id: UUID, renewed_by: Optional[User] = None) -> Subscription:
        """Renew subscription."""
        try:
            subscription = AdvertiserSubscriptionService.get_subscription(subscription_id)
            
            if subscription.status != 'active':
                raise AdvertiserValidationError(f"Cannot renew subscription in status: {subscription.status}")
            
            if subscription.auto_renew == False:
                raise AdvertiserValidationError("Auto-renew is disabled for this subscription")
            
            with transaction.atomic():
                # Calculate new end date
                new_end_date = AdvertiserSubscriptionService._calculate_subscription_end_date(
                    subscription.end_date, subscription.billing_cycle
                )
                
                # Update subscription
                old_end_date = subscription.end_date
                subscription.end_date = new_end_date
                subscription.renewed_at = timezone.now()
                subscription.renewal_count = subscription.renewal_count + 1
                subscription.save(update_fields=['end_date', 'renewed_at', 'renewal_count'])
                
                # Create usage record
                SubscriptionUsage.objects.create(
                    subscription=subscription,
                    usage_type='subscription_renewed',
                    usage_amount=float(subscription.price),
                    description=f'Subscription renewed for {subscription.billing_cycle}',
                    metadata={
                        'old_end_date': old_end_date.isoformat(),
                        'new_end_date': new_end_date.isoformat(),
                        'renewal_count': subscription.renewal_count
                    },
                    created_by=renewed_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=subscription.advertiser,
                    user=renewed_by,
                    title='Subscription Renewed',
                    message=f'Your {subscription.plan.name} subscription has been renewed until {new_end_date}.',
                    notification_type='subscription',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log renewal
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='renew_subscription',
                    object_type='Subscription',
                    object_id=str(subscription.id),
                    user=renewed_by,
                    advertiser=subscription.advertiser,
                    description=f"Renewed subscription: {subscription.plan.name}"
                )
                
                return subscription
                
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
        except Exception as e:
            logger.error(f"Error renewing subscription {subscription_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to renew subscription: {str(e)}")
    
    @staticmethod
    def get_subscription_details(subscription_id: UUID) -> Dict[str, Any]:
        """Get detailed subscription information."""
        try:
            subscription = AdvertiserSubscriptionService.get_subscription(subscription_id)
            
            # Get usage statistics
            usage_stats = AdvertiserSubscriptionService._get_usage_statistics(subscription)
            
            # Get billing information
            billing_info = AdvertiserSubscriptionService._get_billing_info(subscription)
            
            # Get upcoming changes
            upcoming_changes = AdvertiserSubscriptionService._get_upcoming_changes(subscription)
            
            return {
                'subscription_id': str(subscription.id),
                'advertiser_id': str(subscription.advertiser.id),
                'plan': {
                    'id': str(subscription.plan.id),
                    'name': subscription.plan.name,
                    'description': subscription.plan.description,
                    'price': float(subscription.plan.price),
                    'currency': subscription.plan.currency,
                    'billing_cycle': subscription.plan.billing_cycle,
                    'features': subscription.plan.features
                },
                'status': subscription.status,
                'dates': {
                    'start_date': subscription.start_date.isoformat(),
                    'end_date': subscription.end_date.isoformat(),
                    'trial_end_date': subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
                    'cancelled_at': subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
                    'cancellation_effective_date': subscription.cancellation_effective_date.isoformat() if subscription.cancellation_effective_date else None
                },
                'pricing': {
                    'price': float(subscription.price),
                    'currency': subscription.currency,
                    'auto_renew': subscription.auto_renew
                },
                'usage': {
                    'current_usage': subscription.current_usage,
                    'usage_limits': subscription.usage_limits,
                    'usage_statistics': usage_stats
                },
                'billing': billing_info,
                'upcoming_changes': upcoming_changes,
                'metadata': {
                    'created_at': subscription.created_at.isoformat(),
                    'renewal_count': subscription.renewal_count,
                    'upgraded_at': subscription.upgraded_at.isoformat() if subscription.upgraded_at else None,
                    'downgrade_scheduled_at': subscription.downgrade_scheduled_at.isoformat() if subscription.downgrade_scheduled_at else None
                }
            }
            
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
        except Exception as e:
            logger.error(f"Error getting subscription details {subscription_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get subscription details: {str(e)}")
    
    @staticmethod
    def get_subscription_usage(advertiser_id: UUID, usage_type: Optional[str] = None,
                                date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get subscription usage information."""
        try:
            advertiser = AdvertiserSubscriptionService.get_advertiser(advertiser_id)
            
            # Get active subscription
            subscription = Subscription.objects.filter(
                advertiser=advertiser,
                status='active'
            ).first()
            
            if not subscription:
                return {
                    'advertiser_id': str(advertiser_id),
                    'subscription_status': 'no_active_subscription',
                    'message': 'No active subscription found'
                }
            
            # Default date range (current billing cycle)
            if not date_range:
                date_range = {
                    'start_date': subscription.start_date.isoformat(),
                    'end_date': subscription.end_date.isoformat()
                }
            
            start_date = date.fromisoformat(date_range['start_date'])
            end_date = date.fromisoformat(date_range['end_date'])
            
            # Get usage records
            queryset = SubscriptionUsage.objects.filter(
                subscription=subscription,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            if usage_type:
                queryset = queryset.filter(usage_type=usage_type)
            
            # Aggregate usage by type
            usage_by_type = queryset.values('usage_type').annotate(
                total_usage=Sum('usage_amount'),
                count=Count('id')
            )
            
            # Get daily usage trend
            daily_usage = queryset.extra(
                {'date': 'date(created_at)'}
            ).values('date').annotate(
                total_usage=Sum('usage_amount')
            ).order_by('date')
            
            return {
                'advertiser_id': str(advertiser_id),
                'subscription_id': str(subscription.id),
                'plan_name': subscription.plan.name,
                'date_range': date_range,
                'usage_by_type': [
                    {
                        'usage_type': item['usage_type'],
                        'total_usage': float(item['total_usage']),
                        'count': item['count']
                    }
                    for item in usage_by_type
                ],
                'daily_usage': [
                    {
                        'date': item['date'].isoformat(),
                        'total_usage': float(item['total_usage'])
                    }
                    for item in daily_usage
                ],
                'current_usage': subscription.current_usage,
                'usage_limits': subscription.usage_limits
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting subscription usage {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get subscription usage: {str(e)}")
    
    @staticmethod
    def get_subscription_plans() -> List[Dict[str, Any]]:
        """Get available subscription plans."""
        try:
            plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
            
            return [
                {
                    'id': str(plan.id),
                    'name': plan.name,
                    'description': plan.description,
                    'price': float(plan.price),
                    'currency': plan.currency,
                    'billing_cycle': plan.billing_cycle,
                    'features': plan.features,
                    'is_popular': plan.is_popular,
                    'max_users': plan.max_users,
                    'storage_limit': plan.storage_limit,
                    'api_calls_limit': plan.api_calls_limit,
                    'support_level': plan.support_level,
                    'created_at': plan.created_at.isoformat()
                }
                for plan in plans
            ]
            
        except Exception as e:
            logger.error(f"Error getting subscription plans: {str(e)}")
            return []
    
    @staticmethod
    def track_usage(subscription_id: UUID, usage_data: Dict[str, Any],
                    tracked_by: Optional[User] = None) -> SubscriptionUsage:
        """Track subscription usage."""
        try:
            subscription = AdvertiserSubscriptionService.get_subscription(subscription_id)
            
            # Validate usage data
            usage_type = usage_data.get('usage_type')
            if not usage_type:
                raise AdvertiserValidationError("usage_type is required")
            
            usage_amount = usage_data.get('usage_amount', 0)
            if usage_amount < 0:
                raise AdvertiserValidationError("usage_amount must be non-negative")
            
            with transaction.atomic():
                # Create usage record
                usage_record = SubscriptionUsage.objects.create(
                    subscription=subscription,
                    usage_type=usage_type,
                    usage_amount=usage_amount,
                    description=usage_data.get('description', ''),
                    metadata=usage_data.get('metadata', {}),
                    created_by=tracked_by
                )
                
                # Update current usage
                current_usage = subscription.current_usage.copy()
                current_usage[usage_type] = current_usage.get(usage_type, 0) + usage_amount
                subscription.current_usage = current_usage
                subscription.save(update_fields=['current_usage'])
                
                # Check usage limits
                AdvertiserSubscriptionService._check_usage_limits(subscription, usage_type, usage_amount)
                
                return usage_record
                
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
        except Exception as e:
            logger.error(f"Error tracking usage {subscription_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to track usage: {str(e)}")
    
    @staticmethod
    def _calculate_subscription_end_date(start_date: date, billing_cycle: str) -> date:
        """Calculate subscription end date based on billing cycle."""
        try:
            if billing_cycle == 'monthly':
                return start_date + timedelta(days=30)
            elif billing_cycle == 'quarterly':
                return start_date + timedelta(days=90)
            elif billing_cycle == 'annual':
                return start_date + timedelta(days=365)
            else:
                return start_date + timedelta(days=30)  # Default to monthly
                
        except Exception as e:
            logger.error(f"Error calculating subscription end date: {str(e)}")
            return start_date + timedelta(days=30)
    
    @staticmethod
    def _calculate_proration(old_plan: SubscriptionPlan, new_plan: SubscriptionPlan, remaining_days: int) -> Decimal:
        """Calculate proration amount for plan upgrade."""
        try:
            if remaining_days <= 0:
                return Decimal('0.00')
            
            # Calculate daily rates
            old_daily_rate = old_plan.price / 30  # Assuming 30-day month
            new_daily_rate = new_plan.price / 30
            
            # Calculate proration
            remaining_value = old_daily_rate * remaining_days
            new_remaining_cost = new_daily_rate * remaining_days
            
            return new_remaining_cost - remaining_value
            
        except Exception as e:
            logger.error(f"Error calculating proration: {str(e)}")
            return Decimal('0.00')
    
    @staticmethod
    def _get_usage_statistics(subscription: Subscription) -> Dict[str, Any]:
        """Get usage statistics for subscription."""
        try:
            # Get usage in current billing cycle
            usage_records = SubscriptionUsage.objects.filter(
                subscription=subscription,
                created_at__gte=subscription.start_date,
                created_at__lte=subscription.end_date
            )
            
            # Aggregate by type
            usage_by_type = usage_records.values('usage_type').annotate(
                total_usage=Sum('usage_amount'),
                count=Count('id')
            )
            
            return {
                'usage_by_type': [
                    {
                        'usage_type': item['usage_type'],
                        'total_usage': float(item['total_usage']),
                        'count': item['count']
                    }
                    for item in usage_by_type
                ],
                'total_usage_events': usage_records.count()
            }
            
        except Exception as e:
            logger.error(f"Error getting usage statistics: {str(e)}")
            return {'usage_by_type': [], 'total_usage_events': 0}
    
    @staticmethod
    def _get_billing_info(subscription: Subscription) -> Dict[str, Any]:
        """Get billing information for subscription."""
        try:
            # Get recent invoices
            invoices = SubscriptionInvoice.objects.filter(
                subscription=subscription
            ).order_by('-created_at')[:3]
            
            return {
                'next_billing_date': subscription.end_date.isoformat(),
                'next_billing_amount': float(subscription.price),
                'recent_invoices': [
                    {
                        'id': str(invoice.id),
                        'invoice_number': invoice.invoice_number,
                        'amount': float(invoice.amount),
                        'status': invoice.status,
                        'created_at': invoice.created_at.isoformat()
                    }
                    for invoice in invoices
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting billing info: {str(e)}")
            return {'next_billing_date': None, 'next_billing_amount': 0, 'recent_invoices': []}
    
    @staticmethod
    def _get_upcoming_changes(subscription: Subscription) -> Dict[str, Any]:
        """Get upcoming changes for subscription."""
        try:
            changes = []
            
            # Check for scheduled downgrade
            if subscription.pending_plan_id:
                pending_plan = AdvertiserSubscriptionService.get_subscription_plan(subscription.pending_plan_id)
                changes.append({
                    'type': 'downgrade',
                    'effective_date': subscription.end_date.isoformat(),
                    'description': f'Downgrade to {pending_plan.name}',
                    'from_plan': subscription.plan.name,
                    'to_plan': pending_plan.name
                })
            
            # Check for upcoming renewal
            if subscription.auto_renew and subscription.end_date <= date.today() + timedelta(days=7):
                changes.append({
                    'type': 'renewal',
                    'effective_date': subscription.end_date.isoformat(),
                    'description': f'Auto-renewal of {subscription.plan.name}',
                    'plan': subscription.plan.name
                })
            
            return changes
            
        except Exception as e:
            logger.error(f"Error getting upcoming changes: {str(e)}")
            return []
    
    @staticmethod
    def _check_usage_limits(subscription: Subscription, usage_type: str, usage_amount: float) -> None:
        """Check usage limits and send alerts."""
        try:
            usage_limits = subscription.usage_limits
            current_usage = subscription.current_usage
            
            # Get limit for usage type
            limit = usage_limits.get(usage_type)
            if limit is None:
                return
            
            # Check if limit exceeded
            new_usage = current_usage.get(usage_type, 0) + usage_amount
            if new_usage > limit:
                # Send alert
                Notification.objects.create(
                    advertiser=subscription.advertiser,
                    user=subscription.advertiser.user,
                    title='Usage Limit Exceeded',
                    message=f'Your {usage_type} usage has exceeded the limit of {limit}.',
                    notification_type='subscription',
                    priority='high',
                    channels=['in_app', 'email']
                )
            elif new_usage > limit * 0.9:
                # Send warning
                Notification.objects.create(
                    advertiser=subscription.advertiser,
                    user=subscription.advertiser.user,
                    title='Usage Limit Warning',
                    message=f'Your {usage_type} usage is approaching the limit of {limit}.',
                    notification_type='subscription',
                    priority='medium',
                    channels=['in_app']
                )
            
        except Exception as e:
            logger.error(f"Error checking usage limits: {str(e)}")
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_subscription(subscription_id: UUID) -> Subscription:
        """Get subscription by ID."""
        try:
            return Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription {subscription_id} not found")
    
    @staticmethod
    def get_subscription_plan(plan_id: UUID) -> SubscriptionPlan:
        """Get subscription plan by ID."""
        try:
            return SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise AdvertiserNotFoundError(f"Subscription plan {plan_id} not found")
    
    @staticmethod
    def get_subscription_statistics() -> Dict[str, Any]:
        """Get subscription statistics across all advertisers."""
        try:
            # Get total subscriptions
            total_subscriptions = Subscription.objects.count()
            active_subscriptions = Subscription.objects.filter(status='active').count()
            cancelled_subscriptions = Subscription.objects.filter(status='cancelled').count()
            
            # Get subscriptions by plan
            subscriptions_by_plan = Subscription.objects.values('plan__name').annotate(
                count=Count('id')
            )
            
            # Get revenue statistics
            monthly_revenue = Subscription.objects.filter(
                status='active',
                billing_cycle='monthly'
            ).aggregate(total=Sum('price'))['total'] or Decimal('0.00')
            
            annual_revenue = Subscription.objects.filter(
                status='active',
                billing_cycle='annual'
            ).aggregate(total=Sum('price'))['total'] or Decimal('0.00')
            
            quarterly_revenue = Subscription.objects.filter(
                status='active',
                billing_cycle='quarterly'
            ).aggregate(total=Sum('price'))['total'] or Decimal('0.00')
            
            # Get churn rate (simplified)
            total_ended = Subscription.objects.filter(
                cancelled_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            churn_rate = (total_ended / total_subscriptions * 100) if total_subscriptions > 0 else 0
            
            return {
                'total_subscriptions': total_subscriptions,
                'active_subscriptions': active_subscriptions,
                'cancelled_subscriptions': cancelled_subscriptions,
                'subscriptions_by_plan': list(subscriptions_by_plan),
                'revenue': {
                    'monthly': float(monthly_revenue),
                    'quarterly': float(quarterly_revenue),
                    'annual': float(annual_revenue),
                    'total_monthly_equivalent': float(monthly_revenue + quarterly_revenue/3 + annual_revenue/12)
                },
                'churn_rate': churn_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription statistics: {str(e)}")
            return {
                'total_subscriptions': 0,
                'active_subscriptions': 0,
                'cancelled_subscriptions': 0,
                'subscriptions_by_plan': [],
                'revenue': {'monthly': 0, 'quarterly': 0, 'annual': 0, 'total_monthly_equivalent': 0},
                'churn_rate': 0
            }
