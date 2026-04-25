from django.conf import settings
"""
Budget Database Model

This module contains budget-related models for managing
advertiser budgets, spending limits, and financial controls.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class Budget(AdvertiserPortalBaseModel, StatusModel, AuditModel, TrackingModel):
    """
    Main budget model for managing advertiser budgets.
    
    This model stores budget information including limits,
    spending rules, and financial controls.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='budgets',
        help_text="Associated advertiser"
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='budgets',
        help_text="Associated campaign (null for advertiser-level budget)"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Budget name or description"
    )
    
    budget_type = models.CharField(
        max_length=50,
        choices=BudgetTypeEnum.choices(),
        default=BudgetTypeEnum.DAILY,
        help_text="Budget period type"
    )
    
    # Budget amounts
    total_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total budget amount"
    )
    
    daily_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Daily budget limit"
    )
    
    weekly_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Weekly budget limit"
    )
    
    monthly_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monthly budget limit"
    )
    
    # Spending tracking
    total_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount spent"
    )
    
    daily_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Daily amount spent"
    )
    
    weekly_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Weekly amount spent"
    )
    
    monthly_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly amount spent"
    )
    
    remaining_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Remaining budget amount"
    )
    
    # Budget period
    start_date = models.DateTimeField(
        help_text="Budget start date"
    )
    
    end_date = models.DateTimeField(
        help_text="Budget end date"
    )
    
    # Budget controls
    auto_renew = models.BooleanField(
        default=False,
        help_text="Automatically renew budget when exhausted"
    )
    
    pause_on_exhaustion = models.BooleanField(
        default=True,
        help_text="Pause campaigns when budget is exhausted"
    )
    
    overspend_allowed = models.BooleanField(
        default=False,
        help_text="Allow overspending beyond budget limit"
    )
    
    overspend_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Maximum overspend amount allowed"
    )
    
    # Alerts and notifications
    alert_thresholds = models.JSONField(
        default=dict,
        blank=True,
        help_text="Budget alert thresholds (percentage-based)"
    )
    
    notification_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification preferences for budget alerts"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_budgets'
        indexes = [
            models.Index(fields=['advertiser', 'budget_type'], name='idx_advertiser_budget_type_136'),
            models.Index(fields=['campaign', 'budget_type'], name='idx_campaign_budget_type_137'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_138'),
            models.Index(fields=['status'], name='idx_status_139'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.campaign or self.advertiser
        return f"{target} - {self.name} (${self.total_budget})"
    
    def clean(self):
        """Validate budget data."""
        super().clean()
        
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date")
        
        if self.total_budget <= 0:
            raise ValidationError("Total budget must be positive")
        
        if self.overspend_allowed and not self.overspend_limit:
            raise ValidationError("Overspend limit is required when overspend is allowed")
        
        # Validate budget amounts hierarchy
        if self.daily_budget and self.weekly_budget and self.daily_budget > self.weekly_budget:
            raise ValidationError("Daily budget cannot exceed weekly budget")
        
        if self.weekly_budget and self.monthly_budget and self.weekly_budget > self.monthly_budget:
            raise ValidationError("Weekly budget cannot exceed monthly budget")
    
    def update_spend(self, additional_spend: Decimal, spend_type: str = 'total') -> None:
        """Update spending amounts."""
        self.total_spend += additional_spend
        
        if spend_type in ['total', 'daily']:
            self.daily_spend += additional_spend
        
        if spend_type in ['total', 'weekly']:
            self.weekly_spend += additional_spend
        
        if spend_type in ['total', 'monthly']:
            self.monthly_spend += additional_spend
        
        # Update remaining budget
        self.remaining_budget = max(Decimal('0.00'), self.total_budget - self.total_spend)
        
        self.save(update_fields=['total_spend', 'daily_spend', 'weekly_spend', 'monthly_spend', 'remaining_budget'])
    
    def is_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        if self.overspend_allowed:
            return self.total_spend >= (self.total_budget + (self.overspend_limit or Decimal('0.00')))
        return self.total_spend >= self.total_budget
    
    def utilization_rate(self) -> Decimal:
        """Calculate budget utilization rate."""
        if self.total_budget == 0:
            return Decimal('0.00')
        return (self.total_spend / self.total_budget) * Decimal('100')
    
    def get_daily_remaining(self) -> Decimal:
        """Get remaining daily budget."""
        if not self.daily_budget:
            return Decimal('0.00')
        return max(Decimal('0.00'), self.daily_budget - self.daily_spend)
    
    def check_alert_thresholds(self) -> List[str]:
        """Check if any alert thresholds are triggered."""
        alerts = []
        utilization = self.utilization_rate()
        
        for threshold_level, threshold_value in self.alert_thresholds.items():
            if utilization >= threshold_value:
                alerts.append(f"Budget utilization reached {threshold_level}%")
        
        return alerts


class BudgetAlert(AdvertiserPortalBaseModel, AuditModel):
    """
    Budget alert model for tracking budget notifications.
    
    This model stores budget alert history and notification details.
    """
    
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text="Associated budget"
    )
    
    alert_type = models.CharField(
        max_length=50,
        choices=AlertTypeEnum.choices(),
        help_text="Type of alert"
    )
    
    threshold_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Alert threshold percentage"
    )
    
    current_utilization = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Current budget utilization percentage"
    )
    
    alert_message = models.TextField(
        help_text="Alert message content"
    )
    
    notification_sent = models.BooleanField(
        default=False,
        help_text="Whether notification was sent"
    )
    
    notification_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Channels used for notification"
    )
    
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether alert was acknowledged"
    )
    
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='acknowledged_alerts',
        help_text="User who acknowledged the alert"
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Alert acknowledgment timestamp"
    )
    
    resolved = models.BooleanField(
        default=False,
        help_text="Whether alert was resolved"
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Alert resolution timestamp"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_budget_alerts'
        indexes = [
            models.Index(fields=['budget', 'alert_type'], name='idx_budget_alert_type_140'),
            models.Index(fields=['notification_sent'], name='idx_notification_sent_141'),
            models.Index(fields=['acknowledged'], name='idx_acknowledged_142'),
            models.Index(fields=['resolved'], name='idx_resolved_143'),
            models.Index(fields=['created_at'], name='idx_created_at_144'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.budget} - {self.alert_type} ({self.threshold_percentage}%)"


class SpendRule(AdvertiserPortalBaseModel, StatusModel, AuditModel):
    """
    Spend rule model for automated budget controls.
    
    This model defines rules for automated spending adjustments
    and budget management.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='spend_rules',
        help_text="Associated advertiser"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Rule name"
    )
    
    rule_type = models.CharField(
        max_length=50,
        choices=SpendRuleTypeEnum.choices(),
        help_text="Type of spend rule"
    )
    
    trigger_conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conditions that trigger the rule"
    )
    
    actions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Actions to perform when rule is triggered"
    )
    
    priority = models.IntegerField(
        default=100,
        help_text="Rule priority (lower numbers = higher priority)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the rule is currently active"
    )
    
    execution_count = models.IntegerField(
        default=0,
        help_text="Number of times rule has been executed"
    )
    
    last_executed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last execution timestamp"
    )
    
    execution_history = models.JSONField(
        default=list,
        blank=True,
        help_text="History of rule executions"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_spend_rules'
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_145'),
            models.Index(fields=['rule_type'], name='idx_rule_type_146'),
            models.Index(fields=['priority'], name='idx_priority_147'),
            models.Index(fields=['last_executed'], name='idx_last_executed_148'),
        ]
        ordering = ['priority', '-created_at']
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.name}"
    
    def execute_rule(self, context: Dict[str, Any]) -> bool:
        """Execute the spend rule with given context."""
        if not self.is_active:
            return False
        
        # Check if trigger conditions are met
        if not self._check_conditions(context):
            return False
        
        # Execute actions
        success = self._execute_actions(context)
        
        if success:
            self.execution_count += 1
            self.last_executed = timezone.now()
            self.execution_history.append({
                'timestamp': timezone.now().isoformat(),
                'context': context,
                'success': True
            })
            self.save(update_fields=['execution_count', 'last_executed', 'execution_history'])
        
        return success
    
    def _check_conditions(self, context: Dict[str, Any]) -> bool:
        """Check if trigger conditions are met."""
        # Implementation would depend on specific rule types
        # This is a placeholder for condition checking logic
        return True
    
    def _execute_actions(self, context: Dict[str, Any]) -> bool:
        """Execute rule actions."""
        # Implementation would depend on specific actions
        # This is a placeholder for action execution logic
        return True
