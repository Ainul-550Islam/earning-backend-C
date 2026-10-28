"""
api/adapters/subscription.py
Subscription adapter for earning backend platform
"""
from django.db.models import Max
from django.db.models import Min
from django.db.models import Q
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscription_plans(request):
    """Get available subscription plans."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get subscription plans
        from subscription.models import SubscriptionPlan
        plans = SubscriptionPlan.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('sort_order', 'price')
        
        # Get user's current subscription
        user_subscription = _get_user_subscription(request.user, tenant_id)
        
        # Serialize plans
        plan_data = []
        for plan in plans:
            plan_data.append({
                'id': plan.id,
                'name': plan.name,
                'description': plan.description,
                'price': str(plan.price),
                'currency': plan.currency,
                'billing_cycle': plan.billing_cycle,
                'duration_days': plan.duration_days,
                'features': plan.features,
                'limits': plan.limits,
                'is_popular': plan.is_popular,
                'is_recommended': _is_plan_recommended(plan, request.user, tenant_id),
                'discount_percentage': plan.discount_percentage,
                'trial_days': plan.trial_days,
                'setup_fee': str(plan.setup_fee) if plan.setup_fee else '0.00',
                'cancellation_policy': plan.cancellation_policy,
                'upgrade_path': _get_upgrade_path(plan, user_subscription),
                'downgrade_path': _get_downgrade_path(plan, user_subscription),
                'user_status': _get_user_plan_status(plan, user_subscription),
            })
        
        return Response({
            'success': True,
            'data': {
                'plans': plan_data,
                'current_subscription': user_subscription,
                'tenant_id': tenant_id,
                'currency': plans.first().currency if plans.exists() else 'USD',
                'available_cycles': list(plans.values_list('billing_cycle', flat=True).distinct()),
                'summary': _get_plans_summary(plans, user_subscription)
            },
            'message': 'Subscription plans retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error getting subscription plans: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve subscription plans',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_subscription(request):
    """Get user's current subscription."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's subscription
        user_subscription = _get_user_subscription(user, tenant_id)
        
        if not user_subscription:
            return Response({
                'success': True,
                'data': {
                    'user_id': user.id,
                    'tenant_id': tenant_id,
                    'has_subscription': False,
                    'message': 'No active subscription found'
                },
                'message': 'User subscription retrieved successfully'
            }, status=status.HTTP_200_OK)
        
        # Get subscription details
        subscription_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'subscription_id': user_subscription.id,
            'plan': {
                'id': user_subscription.plan.id,
                'name': user_subscription.plan.name,
                'description': user_subscription.plan.description,
                'price': str(user_subscription.plan.price),
                'currency': user_subscription.plan.currency,
                'billing_cycle': user_subscription.plan.billing_cycle,
                'duration_days': user_subscription.plan.duration_days,
                'features': user_subscription.plan.features,
                'limits': user_subscription.plan.limits,
            },
            'status': {
                'status': user_subscription.status,
                'is_active': user_subscription.is_active,
                'is_trial': user_subscription.is_trial,
                'auto_renew': user_subscription.auto_renew,
                'cancellation_pending': user_subscription.cancellation_pending,
            },
            'billing': {
                'start_date': user_subscription.start_date.isoformat(),
                'end_date': user_subscription.end_date.isoformat() if user_subscription.end_date else None,
                'next_billing_date': user_subscription.next_billing_date.isoformat() if user_subscription.next_billing_date else None,
                'last_payment_date': user_subscription.last_payment_date.isoformat() if user_subscription.last_payment_date else None,
                'payment_method': user_subscription.payment_method,
                'payment_status': user_subscription.payment_status,
                'amount_paid': str(user_subscription.amount_paid) if user_subscription.amount_paid else '0.00',
                'next_amount': str(user_subscription.next_amount) if user_subscription.next_amount else '0.00',
            },
            'usage': {
                'days_used': (timezone.now().date() - user_subscription.start_date.date()).days + 1,
                'days_remaining': _get_days_remaining(user_subscription),
                'percentage_used': _get_usage_percentage(user_subscription),
                'current_cycle_usage': _get_current_cycle_usage(user, tenant_id),
                'usage_breakdown': _get_usage_breakdown(user, tenant_id),
            },
            'history': _get_subscription_history(user, tenant_id),
            'available_actions': _get_available_actions(user_subscription),
            'upgrade_options': _get_upgrade_options(user_subscription, tenant_id),
            'cancellation_info': _get_cancellation_info(user_subscription),
        }
        
        return Response({
            'success': True,
            'data': subscription_data,
            'message': 'User subscription retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error getting user subscription: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user subscription',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_subscription(request):
    """Create a new subscription."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        plan_id = data.get('plan_id')
        payment_method = data.get('payment_method')
        
        if not plan_id:
            return Response({
                'success': False,
                'error': 'Plan ID required',
                'details': 'Please provide a plan ID to subscribe to'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not payment_method:
            return Response({
                'success': False,
                'error': 'Payment method required',
                'details': 'Please provide a payment method'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get plan
        from subscription.models import SubscriptionPlan, UserSubscription
        try:
            plan = SubscriptionPlan.objects.get(
                id=plan_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except SubscriptionPlan.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Plan not found',
                'details': f'Subscription plan with ID {plan_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user already has active subscription
        existing_subscription = UserSubscription.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='active'
        ).first()
        
        if existing_subscription:
            return Response({
                'success': False,
                'error': 'Active subscription exists',
                'details': 'You already have an active subscription'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create subscription
        subscription = UserSubscription.objects.create(
            user=user,
            plan=plan,
            status='pending',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=plan.duration_days),
            payment_method=payment_method,
            auto_renew=data.get('auto_renew', True),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Process payment
        payment_result = _process_subscription_payment(subscription, plan, payment_method, data)
        
        if payment_result['success']:
            subscription.status = 'active'
            subscription.amount_paid = payment_result['amount']
            subscription.last_payment_date = timezone.now()
            subscription.next_billing_date = subscription.end_date
            subscription.save()
            
            # Update user features based on plan
            _update_user_subscription_features(user, plan, tenant_id)
            
            # Emit subscription created event
            from api.tasks.integration.event_bus import EventBus
            EventBus.emit('subscription.created', {
                'user_id': user.id,
                'subscription_id': subscription.id,
                'plan_id': plan.id,
                'payment_method': payment_method,
                'tenant_id': tenant_id
            })
            
            return Response({
                'success': True,
                'data': {
                    'subscription_id': subscription.id,
                    'plan': {
                        'id': plan.id,
                        'name': plan.name,
                        'price': str(plan.price),
                        'features': plan.features,
                    },
                    'status': 'active',
                    'start_date': subscription.start_date.isoformat(),
                    'end_date': subscription.end_date.isoformat(),
                    'payment_status': 'paid',
                    'amount_paid': str(subscription.amount_paid),
                },
                'message': 'Subscription created successfully'
            }, status=status.HTTP_201_CREATED)
        else:
            subscription.status = 'payment_failed'
            subscription.save()
            
            return Response({
                'success': False,
                'error': 'Payment failed',
                'details': payment_result.get('error', 'Payment processing failed')
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error creating subscription: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create subscription',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    """Cancel user's subscription."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get user's subscription
        user_subscription = _get_user_subscription(user, tenant_id)
        
        if not user_subscription:
            return Response({
                'success': False,
                'error': 'No active subscription',
                'details': 'You do not have an active subscription to cancel'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if user_subscription.status != 'active':
            return Response({
                'success': False,
                'error': 'Subscription not active',
                'details': 'Your subscription is not currently active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update subscription
        user_subscription.status = 'cancelled'
        user_subscription.cancellation_pending = True
        user_subscription.cancellation_reason = data.get('reason', 'User requested cancellation')
        user_subscription.cancellation_date = timezone.now()
        user_subscription.auto_renew = False
        user_subscription.save()
        
        # Process refund if applicable
        refund_result = _process_subscription_refund(user_subscription, data)
        
        # Remove user features
        _remove_user_subscription_features(user, tenant_id)
        
        # Emit subscription cancelled event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('subscription.cancelled', {
            'user_id': user.id,
            'subscription_id': user_subscription.id,
            'reason': data.get('reason'),
            'refund_processed': refund_result['success'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'subscription_id': user_subscription.id,
                'status': 'cancelled',
                'cancellation_date': user_subscription.cancellation_date.isoformat(),
                'reason': user_subscription.cancellation_reason,
                'refund_info': refund_result,
                'effective_date': user_subscription.end_date.isoformat(),
            },
            'message': 'Subscription cancelled successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error cancelling subscription: {e}")
        return Response({
            'success': False,
            'error': 'Failed to cancel subscription',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_subscription(request):
    """Upgrade user's subscription."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        target_plan_id = data.get('target_plan_id')
        
        if not target_plan_id:
            return Response({
                'success': False,
                'error': 'Target plan ID required',
                'details': 'Please provide a target plan ID to upgrade to'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get current subscription
        user_subscription = _get_user_subscription(user, tenant_id)
        
        if not user_subscription:
            return Response({
                'success': False,
                'error': 'No active subscription',
                'details': 'You do not have an active subscription to upgrade'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get target plan
        from subscription.models import SubscriptionPlan
        try:
            target_plan = SubscriptionPlan.objects.get(
                id=target_plan_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except SubscriptionPlan.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Target plan not found',
                'details': f'Subscription plan with ID {target_plan_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if upgrade is allowed
        if not _can_upgrade_to_plan(user_subscription.plan, target_plan):
            return Response({
                'success': False,
                'error': 'Upgrade not allowed',
                'details': 'You cannot upgrade to this plan from your current plan'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process upgrade
        upgrade_result = _process_subscription_upgrade(user_subscription, target_plan, data)
        
        if upgrade_result['success']:
            # Update subscription
            user_subscription.plan = target_plan
            user_subscription.upgraded_at = timezone.now()
            user_subscription.save()
            
            # Update user features
            _update_user_subscription_features(user, target_plan, tenant_id)
            
            # Emit subscription upgraded event
            from api.tasks.integration.event_bus import EventBus
            EventBus.emit('subscription.upgraded', {
                'user_id': user.id,
                'subscription_id': user_subscription.id,
                'old_plan_id': user_subscription.plan.id,
                'new_plan_id': target_plan.id,
                'tenant_id': tenant_id
            })
            
            return Response({
                'success': True,
                'data': {
                    'subscription_id': user_subscription.id,
                    'old_plan': {
                        'id': user_subscription.plan.id,
                        'name': user_subscription.plan.name,
                    },
                    'new_plan': {
                        'id': target_plan.id,
                        'name': target_plan.name,
                        'price': str(target_plan.price),
                    },
                    'upgraded_at': user_subscription.upgraded_at.isoformat(),
                    'effective_date': user_subscription.next_billing_date.isoformat(),
                    'proration_info': upgrade_result.get('proration', {}),
                },
                'message': 'Subscription upgraded successfully'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Upgrade failed',
                'details': upgrade_result.get('error', 'Upgrade processing failed')
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error upgrading subscription: {e}")
        return Response({
            'success': False,
            'error': 'Failed to upgrade subscription',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_subscription_analytics(request):
    """Get subscription analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get subscription analytics
        from subscription.models import UserSubscription, SubscriptionPlan
        subscriptions = UserSubscription.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('plan', 'user')
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'subscriptions': {
                'total_subscriptions': subscriptions.count(),
                'active_subscriptions': subscriptions.filter(status='active').count(),
                'trial_subscriptions': subscriptions.filter(is_trial=True).count(),
                'cancelled_subscriptions': subscriptions.filter(status='cancelled').count(),
                'new_subscriptions': subscriptions.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
            },
            'revenue': {
                'total_revenue': str(subscriptions.filter(
                    status='active'
                ).aggregate(
                    total=Sum(F('plan__price'))
                )['total'] or Decimal('0')),
                'monthly_recurring': str(subscriptions.filter(
                    status='active',
                    plan__billing_cycle='monthly'
                ).aggregate(
                    total=Sum(F('plan__price'))
                )['total'] or Decimal('0')),
                'annual_recurring': str(subscriptions.filter(
                    status='active',
                    plan__billing_cycle='yearly'
                ).aggregate(
                    total=Sum(F('plan__price'))
                )['total'] or Decimal('0')),
                'average_revenue_per_user': str(subscriptions.filter(
                    status='active'
                ).aggregate(
                    avg_revenue=Avg(F('plan__price'))
                )['avg_revenue'] or Decimal('0')),
            },
            'plan_performance': [
                {
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'subscriptions_count': subscriptions.filter(plan=plan).count(),
                    'active_subscriptions': subscriptions.filter(
                        plan=plan,
                        status='active'
                    ).count(),
                    'conversion_rate': round((subscriptions.filter(
                        plan=plan,
                        status='active'
                    ).count() / max(subscriptions.filter(plan=plan).count(), 1)) * 100, 2),
                    'revenue': str(subscriptions.filter(
                        plan=plan,
                        status='active'
                    ).aggregate(
                        total=Sum(F('plan__price'))
                    )['total'] or Decimal('0')),
                    'churn_rate': _calculate_plan_churn_rate(plan, subscriptions, days),
                }
                for plan in SubscriptionPlan.objects.filter(
                    tenant_id=tenant_id,
                    is_active=True
                ).annotate(
                    subscriptions_count=Count('id')
                ).order_by('-subscriptions_count')
            ],
            'user_metrics': {
                'average_subscription_duration': subscriptions.filter(
                    status='active'
                ).aggregate(
                    avg_duration=Avg(F('end_date') - F('start_date'))
                )['avg_duration'].days if subscriptions.filter(status='active').exists() else 0,
                'trial_conversion_rate': round((subscriptions.filter(
                    is_trial=True,
                    status='active'
                ).count() / max(subscriptions.filter(is_trial=True).count(), 1)) * 100, 2),
                'cancellation_rate': round((subscriptions.filter(
                    status='cancelled'
                ).count() / max(subscriptions.count(), 1)) * 100, 2),
                'upgrade_rate': round((subscriptions.filter(
                    upgraded_at__isnull=False
                ).count() / max(subscriptions.count(), 1)) * 100, 2),
            },
            'trends': _get_subscription_trends(subscriptions, days),
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Subscription analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error getting subscription analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve subscription analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_user_subscription(user, tenant_id):
    """Get user's current subscription."""
    try:
        from subscription.models import UserSubscription
        return UserSubscription.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='active'
        ).select_related('plan').first()
    except Exception:
        return None


def _is_plan_recommended(plan, user, tenant_id):
    """Check if plan is recommended for user."""
    try:
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Check user level and activity
        if ctx.user_level >= 5 and ctx.total_earnings > Decimal('1000'):
            return plan.name in ['Pro', 'Premium']
        elif ctx.user_level >= 3 and ctx.total_earnings > Decimal('500'):
            return plan.name in ['Standard', 'Basic']
        else:
            return plan.name == 'Basic'
    except Exception:
        return False


def _get_upgrade_path(current_plan, user_subscription):
    """Get upgrade path from current plan."""
    if not user_subscription:
        return None
    
    # Simple upgrade logic based on plan hierarchy
    plan_hierarchy = ['Basic', 'Standard', 'Pro', 'Premium']
    
    try:
        current_index = plan_hierarchy.index(current_plan.name)
        next_plans = plan_hierarchy[current_index + 1:]
        return next_plans[:3]  # Return next 3 plans as upgrade options
    except (ValueError, IndexError):
        return []


def _get_downgrade_path(current_plan, user_subscription):
    """Get downgrade path from current plan."""
    if not user_subscription:
        return None
    
    # Simple downgrade logic
    plan_hierarchy = ['Basic', 'Standard', 'Pro', 'Premium']
    
    try:
        current_index = plan_hierarchy.index(current_plan.name)
        previous_plans = plan_hierarchy[:current_index]
        return previous_plans[-3:]  # Return previous 3 plans as downgrade options
    except (ValueError, IndexError):
        return []


def _get_user_plan_status(plan, user_subscription):
    """Get user's status for a specific plan."""
    if not user_subscription:
        return 'not_subscribed'
    
    if user_subscription.plan.id == plan.id:
        if user_subscription.status == 'active':
            return 'current'
        elif user_subscription.status == 'trial':
            return 'trial'
        else:
            return 'expired'
    else:
        return 'available'


def _get_plans_summary(plans, user_subscription):
    """Get summary of plans."""
    if not plans.exists():
        return {}
    
    current_plan = user_subscription.plan if user_subscription else None
    
    return {
        'total_plans': plans.count(),
        'price_range': {
            'min': str(plans.aggregate(min_price=Min(F('price')))['min_price'] or Decimal('0')),
            'max': str(plans.aggregate(max_price=Max(F('price')))['max_price'] or Decimal('0')),
        },
        'most_popular': plans.filter(is_popular=True).first().name if plans.filter(is_popular=True).exists() else None,
        'current_plan': current_plan.name if current_plan else None,
        'can_upgrade': _can_upgrade_from_current(current_plan, plans),
        'available_upgrades': _get_available_upgrades(current_plan, plans),
    }


def _get_days_remaining(subscription):
    """Get days remaining in subscription."""
    if not subscription or not subscription.end_date:
        return 0
    
    remaining = subscription.end_date.date() - timezone.now().date()
    return max(remaining.days, 0)


def _get_usage_percentage(subscription):
    """Get usage percentage of subscription."""
    if not subscription or not subscription.start_date:
        return 0.0
    
    total_days = (subscription.end_date.date() - subscription.start_date.date()).days
    used_days = (timezone.now().date() - subscription.start_date.date()).days
    
    return round((used_days / max(total_days, 1)) * 100, 2)


def _get_current_cycle_usage(user, tenant_id):
    """Get current billing cycle usage."""
    try:
        from subscription.models import UserSubscription
        current_subscription = UserSubscription.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='active'
        ).first()
        
        if not current_subscription:
            return {}
        
        # Get usage from last billing date
        from api.tasks.models import UserTaskCompletion
        usage_start = current_subscription.last_payment_date or current_subscription.start_date
        
        tasks_completed = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=usage_start,
            tenant_id=tenant_id,
            status='completed'
        ).count()
        
        return {
            'tasks_completed': tasks_completed,
            'period_days': (timezone.now().date() - usage_start.date()).days + 1,
            'daily_average': round(tasks_completed / max((timezone.now().date() - usage_start.date()).days + 1, 1), 2),
        }
    except Exception:
        return {}


def _get_usage_breakdown(user, tenant_id):
    """Get detailed usage breakdown."""
    try:
        from subscription.models import UserSubscription
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        from datetime import timedelta
        
        current_subscription = UserSubscription.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='active'
        ).first()
        
        if not current_subscription:
            return {}
        
        # Last 30 days usage
        last_30_days = timezone.now() - timedelta(days=30)
        tasks_last_30 = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=last_30_days,
            tenant_id=tenant_id,
            status='completed'
        ).count()
        
        return {
            'last_30_days': {
                'tasks_completed': tasks_last_30,
                'daily_average': round(tasks_last_30 / 30, 2),
                'peak_day': _get_peak_usage_day(user, tenant_id, 30),
            },
            'subscription_period': {
                'days_used': (timezone.now().date() - current_subscription.start_date.date()).days + 1,
                'days_remaining': _get_days_remaining(current_subscription),
                'usage_percentage': _get_usage_percentage(current_subscription),
            }
        }
    except Exception:
        return {}


def _get_peak_usage_day(user, tenant_id, days):
    """Get peak usage day."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Group by day and find peak
        daily_usage = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=start_date,
            tenant_id=tenant_id,
            status='completed'
        ).extra({
            'day': 'date(completed_at)'
        }).values('day').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return daily_usage.first()['day'].isoformat() if daily_usage.exists() else None
    except Exception:
        return None


def _get_available_actions(subscription):
    """Get available actions for subscription."""
    if not subscription:
        return []
    
    actions = ['view_details', 'download_invoice']
    
    if subscription.status == 'active':
        actions.extend(['cancel', 'upgrade', 'change_payment_method'])
        if subscription.auto_renew:
            actions.append('disable_auto_renew')
        else:
            actions.append('enable_auto_renew')
    
    if subscription.status == 'trial':
        actions.extend(['upgrade_now', 'extend_trial'])
    
    return actions


def _get_upgrade_options(subscription, tenant_id):
    """Get upgrade options."""
    if not subscription:
        return []
    
    from subscription.models import SubscriptionPlan
    current_plan = subscription.plan
    
    # Get plans that are upgrades
    upgrade_plans = SubscriptionPlan.objects.filter(
        tenant_id=tenant_id,
        is_active=True,
        price__gt=current_plan.price
    ).order_by('price')
    
    return [
        {
            'id': plan.id,
            'name': plan.name,
            'price': str(plan.price),
            'features': plan.features,
            'upgrade_benefits': _get_upgrade_benefits(current_plan, plan),
        }
        for plan in upgrade_plans
    ]


def _get_upgrade_benefits(current_plan, target_plan):
    """Get upgrade benefits."""
    benefits = []
    
    # Compare features
    current_features = set(current_plan.features or [])
    target_features = set(target_plan.features or [])
    
    new_features = target_features - current_features
    for feature in new_features:
        benefits.append(f"Access to {feature}")
    
    return benefits


def _get_cancellation_info(subscription):
    """Get cancellation information."""
    if not subscription:
        return {}
    
    return {
        'cancellation_pending': subscription.cancellation_pending,
        'cancellation_date': subscription.cancellation_date.isoformat() if subscription.cancellation_date else None,
        'cancellation_reason': subscription.cancellation_reason,
        'refund_eligible': _is_refund_eligible(subscription),
        'refund_policy': subscription.plan.cancellation_policy if subscription.plan else None,
        'effective_date': subscription.end_date.isoformat() if subscription.end_date else None,
    }


def _process_subscription_payment(subscription, plan, payment_method, data):
    """Process subscription payment."""
    try:
        # Simulate payment processing
        amount = plan.price
        
        # Apply discount if applicable
        discount_code = data.get('discount_code')
        if discount_code:
            discount = _apply_discount_code(discount_code, plan, subscription.tenant_id)
            if discount['success']:
                amount = amount * (1 - discount['percentage'] / 100)
        
        # Process payment based on method
        if payment_method == 'credit_card':
            return _process_credit_card_payment(amount, data)
        elif payment_method == 'paypal':
            return _process_paypal_payment(amount, data)
        elif payment_method == 'crypto':
            return _process_crypto_payment(amount, data)
        else:
            return {
                'success': False,
                'error': 'Unsupported payment method',
                'details': f'Payment method {payment_method} is not supported'
            }
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error processing payment: {e}")
        return {
            'success': False,
            'error': 'Payment processing failed',
            'details': str(e)
        }


def _process_credit_card_payment(amount, data):
    """Process credit card payment."""
    # Simulate credit card payment
    return {
        'success': True,
        'amount': amount,
        'payment_method': 'credit_card',
        'transaction_id': f"cc_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
        'masked_card': f"****-****-****-{data.get('last4', '1234')}",
    }


def _process_paypal_payment(amount, data):
    """Process PayPal payment."""
    # Simulate PayPal payment
    return {
        'success': True,
        'amount': amount,
        'payment_method': 'paypal',
        'transaction_id': f"pp_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
        'paypal_email': data.get('paypal_email', ''),
    }


def _process_crypto_payment(amount, data):
    """Process cryptocurrency payment."""
    # Simulate crypto payment
    return {
        'success': True,
        'amount': amount,
        'payment_method': 'crypto',
        'transaction_id': f"crypto_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
        'crypto_address': data.get('crypto_address', ''),
        'crypto_type': data.get('crypto_type', 'BTC'),
    }


def _apply_discount_code(discount_code, plan, tenant_id):
    """Apply discount code."""
    # Simulate discount code validation
    if discount_code == 'WELCOME10':
        return {
            'success': True,
            'percentage': 10,
            'description': '10% welcome discount',
        }
    elif discount_code == 'SAVE20':
        return {
            'success': True,
            'percentage': 20,
            'description': '20% savings discount',
        }
    else:
        return {
            'success': False,
            'error': 'Invalid discount code',
        }


def _process_subscription_refund(subscription, data):
    """Process subscription refund."""
    try:
        if not _is_refund_eligible(subscription):
            return {
                'success': False,
                'error': 'Refund not eligible',
                'details': 'This subscription is not eligible for refund'
            }
        
        # Calculate refund amount
        days_used = (timezone.now().date() - subscription.start_date.date()).days
        total_days = (subscription.end_date.date() - subscription.start_date.date()).days
        
        if days_used < 7:  # No refund for less than 7 days
            return {
                'success': False,
                'error': 'Refund period not met',
                'details': 'Refunds only available after 7 days of usage'
            }
        
        refund_percentage = min(days_used / total_days, 0.5)  # Max 50% refund
        refund_amount = subscription.plan.price * Decimal(str(refund_percentage))
        
        # Process refund
        refund_result = _process_refund_payment(refund_amount, subscription, data)
        
        return {
            'success': True,
            'refund_amount': str(refund_amount),
            'refund_percentage': refund_percentage,
            'refund_method': refund_result['method'],
            'refund_id': refund_result['refund_id'],
            'processed_at': timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"[SubscriptionAdapter] Error processing refund: {e}")
        return {
            'success': False,
            'error': 'Refund processing failed',
            'details': str(e)
        }


def _process_refund_payment(amount, subscription, data):
    """Process refund payment."""
    # Simulate refund processing
    return {
        'success': True,
        'amount': amount,
        'method': 'original_payment_method',
        'refund_id': f"refund_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
    }


def _is_refund_eligible(subscription):
    """Check if subscription is eligible for refund."""
    if not subscription:
        return False
    
    # Check cancellation policy
    if subscription.plan and subscription.plan.cancellation_policy == 'no_refund':
        return False
    
    # Check if within refund period
    if subscription.cancellation_date:
        days_since_cancellation = (timezone.now().date() - subscription.cancellation_date.date()).days
        return days_since_cancellation <= 30  # 30 days refund window
    
    return False


def _can_upgrade_to_plan(current_plan, target_plan):
    """Check if upgrade is allowed."""
    if not current_plan or not target_plan:
        return False
    
    # Simple hierarchy check
    plan_hierarchy = ['Basic', 'Standard', 'Pro', 'Premium']
    
    try:
        current_index = plan_hierarchy.index(current_plan.name)
        target_index = plan_hierarchy.index(target_plan.name)
        return target_index > current_index
    except (ValueError, IndexError):
        return False


def _can_upgrade_from_current(current_plan, plans):
    """Check if user can upgrade from current plan."""
    if not current_plan:
        return False
    
    from subscription.models import SubscriptionPlan
    upgrade_plans = SubscriptionPlan.objects.filter(
        price__gt=current_plan.price,
        is_active=True
    ).exists()
    
    return upgrade_plans


def _update_user_subscription_features(user, plan, tenant_id):
    """Update user features based on subscription plan."""
    try:
        # Update user cache with subscription features
        features = plan.features or {}
        
        # Cache subscription features
        cache.set(f'subscription_features_{user.id}', features, timeout=86400)
        
        # Update user level if applicable
        if 'premium_features' in features:
            user.level = max(getattr(user, 'level', 1), 5)
            user.save()
        
    except Exception:
        pass


def _remove_user_subscription_features(user, tenant_id):
    """Remove user subscription features."""
    try:
        # Clear subscription features cache
        cache.delete(f'subscription_features_{user.id}')
        
        # Reset user level to basic
        user.level = max(getattr(user, 'level', 1), 1)
        user.save()
        
    except Exception:
        pass


def _get_subscription_history(user, tenant_id):
    """Get user's subscription history."""
    try:
        from subscription.models import UserSubscription
        return UserSubscription.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('plan').order_by('-created_at')[:10]
    except Exception:
        return []


def _calculate_plan_churn_rate(plan, subscriptions, days):
    """Calculate churn rate for a plan."""
    try:
        # Get subscriptions for this plan in the period
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        plan_subscriptions = subscriptions.filter(
            plan=plan,
            created_at__gte=start_date
        )
        
        if not plan_subscriptions.exists():
            return 0.0
        
        # Calculate churn rate
        cancelled_subscriptions = plan_subscriptions.filter(status='cancelled').count()
        total_subscriptions = plan_subscriptions.count()
        
        return round((cancelled_subscriptions / max(total_subscriptions, 1)) * 100, 2)
    except Exception:
        return 0.0


def _get_subscription_trends(subscriptions, days):
    """Get subscription trends."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import TruncDay
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Daily subscription trends
        daily_trends = subscriptions.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            new_subscriptions=Count('id'),
            cancelled_subscriptions=Count('id', filter=Q(status='cancelled')),
            active_subscriptions=Count('id', filter=Q(status='active'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'new_subscriptions': trend['new_subscriptions'],
                'cancelled_subscriptions': trend['cancelled_subscriptions'],
                'active_subscriptions': trend['active_subscriptions'],
                'net_growth': trend['new_subscriptions'] - trend['cancelled_subscriptions'],
            }
            for trend in daily_trends
        ]
    except Exception:
        return []
