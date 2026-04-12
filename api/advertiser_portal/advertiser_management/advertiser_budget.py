"""
Advertiser Budget Management

This module handles budget management for advertisers including budget allocation,
spend tracking, budget alerts, and budget optimization recommendations.
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

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.budget_model import Budget as BudgetAllocation, BudgetAlert, SpendRule as BudgetHistory
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserBudgetService:
    """Service for managing advertiser budget operations."""
    
    @staticmethod
    def allocate_budget(advertiser_id: UUID, budget_data: Dict[str, Any],
                        allocated_by: Optional[User] = None) -> BudgetAllocation:
        """Allocate budget for advertiser."""
        try:
            advertiser = AdvertiserBudgetService.get_advertiser(advertiser_id)
            
            # Validate budget data
            amount = Decimal(str(budget_data.get('amount', 0)))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            budget_type = budget_data.get('budget_type', 'campaign')
            if budget_type not in ['campaign', 'monthly', 'quarterly', 'annual']:
                raise AdvertiserValidationError("Invalid budget type")
            
            with transaction.atomic():
                # Create budget allocation
                budget_allocation = BudgetAllocation.objects.create(
                    advertiser=advertiser,
                    budget_type=budget_type,
                    amount=amount,
                    allocated_amount=amount,
                    remaining_amount=amount,
                    currency=budget_data.get('currency', 'USD'),
                    start_date=budget_data.get('start_date', date.today()),
                    end_date=budget_data.get('end_date'),
                    campaign_id=budget_data.get('campaign_id'),
                    description=budget_data.get('description', f'{budget_type.title()} budget allocation'),
                    auto_renew=budget_data.get('auto_renew', False),
                    status='active',
                    created_by=allocated_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=allocated_by,
                    title='Budget Allocated',
                    message=f'{budget_type.title()} budget of {budget_allocation.currency} {amount} has been allocated.',
                    notification_type='budget',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log allocation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    budget_allocation,
                    allocated_by,
                    description=f"Allocated {budget_type} budget: {amount}"
                )
                
                return budget_allocation
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error allocating budget {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to allocate budget: {str(e)}")
    
    @staticmethod
    def spend_budget(budget_id: UUID, spend_data: Dict[str, Any],
                    spent_by: Optional[User] = None) -> bool:
        """Spend from allocated budget."""
        try:
            budget_allocation = AdvertiserBudgetService.get_budget_allocation(budget_id)
            
            # Validate spend data
            amount = Decimal(str(spend_data.get('amount', 0)))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            # Check sufficient budget
            if budget_allocation.remaining_amount < amount:
                raise AdvertiserValidationError("Insufficient budget remaining")
            
            with transaction.atomic():
                # Create budget history record
                budget_history = BudgetHistory.objects.create(
                    budget_allocation=budget_allocation,
                    action='spend',
                    amount=-amount,  # Negative for spending
                    description=spend_data.get('description', 'Budget spend'),
                    campaign_id=spend_data.get('campaign_id'),
                    created_by=spent_by
                )
                
                # Update budget allocation
                budget_allocation.remaining_amount -= amount
                budget_allocation.spent_amount += amount
                budget_allocation.last_spent_at = timezone.now()
                budget_allocation.save(update_fields=['remaining_amount', 'spent_amount', 'last_spent_at'])
                
                # Check budget alerts
                if budget_allocation.remaining_amount <= 0:
                    # Budget exhausted
                    budget_allocation.status = 'exhausted'
                    budget_allocation.save(update_fields=['status'])
                    
                    Notification.objects.create(
                        advertiser=budget_allocation.advertiser,
                        user=budget_allocation.advertiser.user,
                        title='Budget Exhausted',
                        message=f'Your {budget_allocation.budget_type} budget has been exhausted.',
                        notification_type='budget',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                elif budget_allocation.remaining_amount <= budget_allocation.allocated_amount * 0.2:
                    # Low budget warning
                    Notification.objects.create(
                        advertiser=budget_allocation.advertiser,
                        user=budget_allocation.advertiser.user,
                        title='Low Budget Warning',
                        message=f'Your {budget_allocation.budget_type} budget is running low.',
                        notification_type='budget',
                        priority='medium',
                        channels=['in_app']
                    )
                
                # Log spend
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='spend_budget',
                    object_type='BudgetAllocation',
                    object_id=str(budget_allocation.id),
                    user=spent_by,
                    advertiser=budget_allocation.advertiser,
                    description=f"Spent from budget: {amount}"
                )
                
                return True
                
        except BudgetAllocation.DoesNotExist:
            raise AdvertiserNotFoundError(f"Budget allocation {budget_id} not found")
        except Exception as e:
            logger.error(f"Error spending budget {budget_id}: {str(e)}")
            return False
    
    @staticmethod
    def adjust_budget(budget_id: UUID, adjustment_data: Dict[str, Any],
                     adjusted_by: Optional[User] = None) -> bool:
        """Adjust allocated budget."""
        try:
            budget_allocation = AdvertiserBudgetService.get_budget_allocation(budget_id)
            
            # Validate adjustment data
            new_amount = Decimal(str(adjustment_data.get('new_amount', 0)))
            if new_amount <= 0:
                raise AdvertiserValidationError("new_amount must be positive")
            
            adjustment_type = adjustment_data.get('adjustment_type', 'manual')
            if adjustment_type not in ['manual', 'increase', 'decrease', 'correction']:
                raise AdvertiserValidationError("Invalid adjustment type")
            
            with transaction.atomic():
                old_amount = budget_allocation.allocated_amount
                adjustment_amount = new_amount - old_amount
                
                # Create budget history record
                budget_history = BudgetHistory.objects.create(
                    budget_allocation=budget_allocation,
                    action='adjust',
                    amount=adjustment_amount,
                    description=adjustment_data.get('description', f'{adjustment_type.title()} budget adjustment'),
                    created_by=adjusted_by
                )
                
                # Update budget allocation
                budget_allocation.allocated_amount = new_amount
                budget_allocation.remaining_amount += adjustment_amount
                budget_allocation.save(update_fields=['allocated_amount', 'remaining_amount'])
                
                # Reactivate if previously exhausted
                if budget_allocation.status == 'exhausted' and budget_allocation.remaining_amount > 0:
                    budget_allocation.status = 'active'
                    budget_allocation.save(update_fields=['status'])
                
                # Send notification for significant adjustments
                if abs(adjustment_amount) >= new_amount * 0.2:
                    Notification.objects.create(
                        advertiser=budget_allocation.advertiser,
                        user=adjusted_by,
                        title='Budget Adjusted',
                        message=f'Your {budget_allocation.budget_type} budget has been adjusted by {budget_allocation.currency} {adjustment_amount}.',
                        notification_type='budget',
                        priority='high',
                        channels=['in_app']
                    )
                
                # Log adjustment
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='adjust_budget',
                    object_type='BudgetAllocation',
                    object_id=str(budget_allocation.id),
                    user=adjusted_by,
                    advertiser=budget_allocation.advertiser,
                    description=f"Adjusted budget: {old_amount} -> {new_amount}"
                )
                
                return True
                
        except BudgetAllocation.DoesNotExist:
            raise AdvertiserNotFoundError(f"Budget allocation {budget_id} not found")
        except Exception as e:
            logger.error(f"Error adjusting budget {budget_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_budget_summary(advertiser_id: UUID, budget_type: Optional[str] = None) -> Dict[str, Any]:
        """Get budget summary for advertiser."""
        try:
            advertiser = AdvertiserBudgetService.get_advertiser(advertiser_id)
            
            # Filter budget allocations
            queryset = BudgetAllocation.objects.filter(advertiser=advertiser)
            if budget_type:
                queryset = queryset.filter(budget_type=budget_type)
            
            # Aggregate budget data
            total_allocated = queryset.aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
            total_spent = queryset.aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
            total_remaining = queryset.aggregate(total=Sum('remaining_amount'))['total'] or Decimal('0.00')
            
            # Get budget by type
            budget_by_type = queryset.values('budget_type').annotate(
                allocated_amount=Sum('allocated_amount'),
                spent_amount=Sum('spent_amount'),
                remaining_amount=Sum('remaining_amount'),
                count=Count('id')
            )
            
            # Get active budgets
            active_budgets = queryset.filter(status='active').count()
            exhausted_budgets = queryset.filter(status='exhausted').count()
            
            # Calculate utilization
            utilization = (total_spent / total_allocated * 100) if total_allocated > 0 else 0
            
            return {
                'advertiser_id': str(advertiser_id),
                'budget_summary': {
                    'total_allocated': float(total_allocated),
                    'total_spent': float(total_spent),
                    'total_remaining': float(total_remaining),
                    'utilization': utilization,
                    'active_budgets': active_budgets,
                    'exhausted_budgets': exhausted_budgets
                },
                'budget_by_type': [
                    {
                        'budget_type': item['budget_type'],
                        'allocated_amount': float(item['allocated_amount']),
                        'spent_amount': float(item['spent_amount']),
                        'remaining_amount': float(item['remaining_amount']),
                        'count': item['count'],
                        'utilization': float((item['spent_amount'] / item['allocated_amount'] * 100) if item['allocated_amount'] > 0 else 0)
                    }
                    for item in budget_by_type
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting budget summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get budget summary: {str(e)}")
    
    @staticmethod
    def get_budget_history(budget_id: UUID, filters: Optional[Dict[str, Any]] = None,
                          page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get budget history."""
        try:
            budget_allocation = AdvertiserBudgetService.get_budget_allocation(budget_id)
            
            queryset = BudgetHistory.objects.filter(budget_allocation=budget_allocation)
            
            # Apply filters
            if filters:
                if 'action' in filters:
                    queryset = queryset.filter(action=filters['action'])
                if 'date_from' in filters:
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(description__icontains=search)
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            history_records = queryset[offset:offset + page_size].order_by('-created_at')
            
            return {
                'budget_id': str(budget_id),
                'budget_type': budget_allocation.budget_type,
                'budget_history': [
                    {
                        'id': str(record.id),
                        'action': record.action,
                        'amount': float(record.amount),
                        'description': record.description,
                        'campaign_id': str(record.campaign_id) if record.campaign_id else None,
                        'created_at': record.created_at.isoformat()
                    }
                    for record in history_records
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
            
        except BudgetAllocation.DoesNotExist:
            raise AdvertiserNotFoundError(f"Budget allocation {budget_id} not found")
        except Exception as e:
            logger.error(f"Error getting budget history {budget_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get budget history: {str(e)}")
    
    @staticmethod
    def get_budget_performance(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get budget performance analysis."""
        try:
            advertiser = AdvertiserBudgetService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get budget allocations in date range
            budget_allocations = BudgetAllocation.objects.filter(
                advertiser=advertiser,
                start_date__lte=end_date,
                end_date__gte=start_date
            )
            
            # Get budget history in date range
            budget_history = BudgetHistory.objects.filter(
                budget_allocation__in=budget_allocations,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Aggregate daily spend
            daily_spend = budget_history.filter(action='spend').extra(
                {'date': 'date(created_at)'}
            ).values('date').annotate(
                total_spend=Sum('amount')
            ).order_by('date')
            
            # Calculate performance metrics
            total_allocated = budget_allocations.aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
            total_spent = abs(budget_history.filter(action='spend').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
            
            # Get campaign performance
            from ..database_models.campaign_model import Campaign
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_impressions = campaigns.aggregate(total=Sum('total_impressions'))['total'] or 0
            total_clicks = campaigns.aggregate(total=Sum('total_clicks'))['total'] or 0
            total_conversions = campaigns.aggregate(total=Sum('total_conversions'))['total'] or 0
            
            # Calculate efficiency metrics
            cpm = (total_spent / total_impressions * 1000) if total_impressions > 0 else 0
            cpc = (total_spent / total_clicks) if total_clicks > 0 else 0
            cpa = (total_spent / total_conversions) if total_conversions > 0 else 0
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'budget_performance': {
                    'total_allocated': float(total_allocated),
                    'total_spent': float(total_spent),
                    'budget_utilization': float((total_spent / total_allocated * 100) if total_allocated > 0 else 0),
                    'remaining_budget': float(total_allocated - total_spent)
                },
                'campaign_performance': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'ctr': (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
                    'conversion_rate': (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
                },
                'efficiency_metrics': {
                    'cpm': float(cpm),
                    'cpc': float(cpc),
                    'cpa': float(cpa)
                },
                'daily_spend': [
                    {
                        'date': item['date'].isoformat(),
                        'total_spend': float(abs(item['total_spend']))
                    }
                    for item in daily_spend
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting budget performance {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get budget performance: {str(e)}")
    
    @staticmethod
    def get_budget_recommendations(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get budget optimization recommendations."""
        try:
            advertiser = AdvertiserBudgetService.get_advertiser(advertiser_id)
            
            recommendations = []
            
            # Get recent performance
            performance = AdvertiserBudgetService.get_budget_performance(advertiser_id)
            
            # Analyze budget utilization
            utilization = performance['budget_performance']['budget_utilization']
            
            if utilization < 50:
                recommendations.append({
                    'type': 'underutilized_budget',
                    'priority': 'medium',
                    'title': 'Underutilized Budget',
                    'description': f'Your budget utilization is only {utilization:.1f}%. Consider increasing spend or reducing budget.',
                    'potential_impact': 'Could improve campaign reach and performance',
                    'action_items': [
                        'Increase daily budget for high-performing campaigns',
                        'Launch new campaigns to utilize remaining budget',
                        'Consider reallocating budget to better performing channels'
                    ]
                })
            elif utilization > 90:
                recommendations.append({
                    'type': 'budget_exhaustion_risk',
                    'priority': 'high',
                    'title': 'Budget Exhaustion Risk',
                    'description': f'Your budget utilization is high at {utilization:.1f}%. Budget may be exhausted soon.',
                    'potential_impact': 'Campaigns may pause unexpectedly',
                    'action_items': [
                        'Increase budget allocation',
                        'Optimize bids to improve efficiency',
                        'Pause underperforming campaigns to reallocate budget'
                    ]
                })
            
            # Analyze efficiency metrics
            cpa = performance['efficiency_metrics']['cpa']
            if cpa > 50:  # Threshold example
                recommendations.append({
                    'type': 'high_cpa',
                    'priority': 'high',
                    'title': 'High Cost Per Acquisition',
                    'description': f'Your CPA is ${cpa:.2f}, which is above optimal range.',
                    'potential_impact': 'Budget efficiency could be improved',
                    'action_items': [
                        'Review targeting settings',
                        'Optimize ad creatives',
                        'Adjust bidding strategy',
                        'Improve landing page experience'
                    ]
                })
            
            # Analyze campaign performance
            ctr = performance['campaign_performance']['ctr']
            if ctr < 1.0:  # Threshold example
                recommendations.append({
                    'type': 'low_ctr',
                    'priority': 'medium',
                    'title': 'Low Click-Through Rate',
                    'description': f'Your CTR is {ctr:.2f}%, which is below industry average.',
                    'potential_impact': 'Better engagement could improve ROI',
                    'action_items': [
                        'Test different ad creatives',
                        'Refine targeting parameters',
                        'Improve ad copy and visuals',
                        'A/B test different ad formats'
                    ]
                })
            
            # Get budget allocation recommendations
            budget_summary = AdvertiserBudgetService.get_budget_summary(advertiser_id)
            
            for budget_type_data in budget_summary['budget_by_type']:
                if budget_type_data['utilization'] > 95:
                    recommendations.append({
                        'type': 'budget_reallocation',
                        'priority': 'medium',
                        'title': f'{budget_type_data["budget_type"].title()} Budget Optimization',
                        'description': f'{budget_type_data["budget_type"].title()} budget is nearly exhausted ({budget_type_data["utilization"]:.1f}% utilized).',
                        'potential_impact': 'Reallocating budget could improve overall performance',
                        'action_items': [
                            f'Reallocate budget from {budget_type_data["budget_type"]} to better performing channels',
                            'Review and optimize {budget_type_data["budget_type"]} campaigns',
                            'Consider increasing total budget allocation'
                        ]
                    })
            
            return recommendations
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting budget recommendations {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def check_budget_health(budget_id: UUID) -> Dict[str, Any]:
        """Check budget health status."""
        try:
            budget_allocation = AdvertiserBudgetService.get_budget_allocation(budget_id)
            
            health_score = 100.0
            issues = []
            
            # Check utilization
            utilization = (budget_allocation.spent_amount / budget_allocation.allocated_amount * 100) if budget_allocation.allocated_amount > 0 else 0
            
            if utilization > 90:
                health_score -= 30
                issues.append({
                    'type': 'high_utilization',
                    'severity': 'high',
                    'message': f'Budget utilization is {utilization:.1f}%'
                })
            elif utilization < 20:
                health_score -= 15
                issues.append({
                    'type': 'low_utilization',
                    'severity': 'medium',
                    'message': f'Budget utilization is only {utilization:.1f}%'
                })
            
            # Check status
            if budget_allocation.status == 'exhausted':
                health_score -= 40
                issues.append({
                    'type': 'exhausted',
                    'severity': 'critical',
                    'message': 'Budget is exhausted'
                })
            elif budget_allocation.status == 'paused':
                health_score -= 20
                issues.append({
                    'type': 'paused',
                    'severity': 'medium',
                    'message': 'Budget is paused'
                })
            
            # Check time remaining
            if budget_allocation.end_date:
                days_remaining = (budget_allocation.end_date - date.today()).days
                if days_remaining <= 7 and days_remaining > 0:
                    health_score -= 10
                    issues.append({
                        'type': 'expiring_soon',
                        'severity': 'medium',
                        'message': f'Budget expires in {days_remaining} days'
                    })
                elif days_remaining <= 0:
                    health_score -= 25
                    issues.append({
                        'type': 'expired',
                        'severity': 'high',
                        'message': 'Budget has expired'
                    })
            
            # Determine health status
            if health_score >= 80:
                health_status = 'excellent'
            elif health_score >= 60:
                health_status = 'good'
            elif health_score >= 40:
                health_status = 'fair'
            else:
                health_status = 'poor'
            
            return {
                'budget_id': str(budget_id),
                'budget_type': budget_allocation.budget_type,
                'health_score': max(0, health_score),
                'health_status': health_status,
                'utilization': utilization,
                'issues': issues,
                'recommendations': AdvertiserBudgetService._get_health_recommendations(issues)
            }
            
        except BudgetAllocation.DoesNotExist:
            raise AdvertiserNotFoundError(f"Budget allocation {budget_id} not found")
        except Exception as e:
            logger.error(f"Error checking budget health {budget_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to check budget health: {str(e)}")
    
    @staticmethod
    def _get_health_recommendations(issues: List[Dict[str, Any]]) -> List[str]:
        """Get recommendations based on health issues."""
        recommendations = []
        
        for issue in issues:
            if issue['type'] == 'high_utilization':
                recommendations.append('Consider increasing budget allocation or optimizing spend efficiency')
            elif issue['type'] == 'low_utilization':
                recommendations.append('Increase campaign spend or reallocate budget to other channels')
            elif issue['type'] == 'exhausted':
                recommendations.append('Add more budget immediately to continue campaigns')
            elif issue['type'] == 'expiring_soon':
                recommendations.append('Renew budget allocation before expiration')
            elif issue['type'] == 'expired':
                recommendations.append('Create new budget allocation to resume campaigns')
        
        return recommendations
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_budget_allocation(budget_id: UUID) -> BudgetAllocation:
        """Get budget allocation by ID."""
        try:
            return BudgetAllocation.objects.get(id=budget_id)
        except BudgetAllocation.DoesNotExist:
            raise AdvertiserNotFoundError(f"Budget allocation {budget_id} not found")
    
    @staticmethod
    def get_budget_statistics() -> Dict[str, Any]:
        """Get budget statistics across all advertisers."""
        try:
            # Get total budget statistics
            total_allocated = BudgetAllocation.objects.aggregate(
                total=Sum('allocated_amount')
            )['total'] or Decimal('0.00')
            
            total_spent = BudgetAllocation.objects.aggregate(
                total=Sum('spent_amount')
            )['total'] or Decimal('0.00')
            
            total_remaining = BudgetAllocation.objects.aggregate(
                total=Sum('remaining_amount')
            )['total'] or Decimal('0.00')
            
            # Get budget by type
            budget_by_type = BudgetAllocation.objects.values('budget_type').annotate(
                allocated_amount=Sum('allocated_amount'),
                spent_amount=Sum('spent_amount'),
                remaining_amount=Sum('remaining_amount'),
                count=Count('id')
            )
            
            # Get budget status distribution
            budget_by_status = BudgetAllocation.objects.values('status').annotate(
                count=Count('id')
            )
            
            # Get exhausted budgets
            exhausted_budgets = BudgetAllocation.objects.filter(
                status='exhausted'
            ).count()
            
            # Get expiring budgets (within 7 days)
            expiring_soon = BudgetAllocation.objects.filter(
                end_date__lte=date.today() + timezone.timedelta(days=7),
                end_date__gt=date.today()
            ).count()
            
            return {
                'total_allocated': float(total_allocated),
                'total_spent': float(total_spent),
                'total_remaining': float(total_remaining),
                'budget_utilization': float((total_spent / total_allocated * 100) if total_allocated > 0 else 0),
                'exhausted_budgets': exhausted_budgets,
                'expiring_soon': expiring_soon,
                'budget_by_type': list(budget_by_type),
                'budget_by_status': list(budget_by_status)
            }
            
        except Exception as e:
            logger.error(f"Error getting budget statistics: {str(e)}")
            return {
                'total_allocated': 0,
                'total_spent': 0,
                'total_remaining': 0,
                'budget_utilization': 0,
                'exhausted_budgets': 0,
                'expiring_soon': 0,
                'budget_by_type': [],
                'budget_by_status': []
            }
