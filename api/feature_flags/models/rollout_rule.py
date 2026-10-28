"""
Rollout Rule model for Feature Flags & A/B Testing.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .base import BaseModel
from .feature_flag import FeatureFlag


class RolloutRule(BaseModel):
    """
    Model for rollout rules for feature flags.
    """
    
    class RuleType(models.TextChoices):
        USER_ID = 'user_id', 'User ID'
        EMAIL = 'email', 'Email'
        SEGMENT = 'segment', 'Segment'
        ATTRIBUTE = 'attribute', 'Attribute'
        PERCENTAGE = 'percentage', 'Percentage'
        CUSTOM = 'custom', 'Custom'
    
    class Operator(models.TextChoices):
        EQUALS = 'equals', 'Equals'
        NOT_EQUALS = 'not_equals', 'Not Equals'
        CONTAINS = 'contains', 'Contains'
        NOT_CONTAINS = 'not_contains', 'Not Contains'
        STARTS_WITH = 'starts_with', 'Starts With'
        ENDS_WITH = 'ends_with', 'Ends With'
        GREATER_THAN = 'greater_than', 'Greater Than'
        LESS_THAN = 'less_than', 'Less Than'
        IN = 'in', 'In'
        NOT_IN = 'not_in', 'Not In'
    
    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='rollout_rules')
    
    # Rule type
    rule_type = models.CharField(max_length=50, choices=RuleType.choices)
    
    # Field to check
    field = models.CharField(max_length=255)
    
    # Operator
    operator = models.CharField(max_length=50, choices=Operator.choices)
    
    # Value to compare against
    value = models.JSONField()
    
    # Priority (higher = evaluated first)
    priority = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    # Is this rule active?
    is_active = models.BooleanField(default=True)
    
    # Description
    description = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = 'Rollout Rule'
        verbose_name_plural = 'Rollout Rules'
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['flag'], name='rule_flag_idx'),
            models.Index(fields=['rule_type'], name='rule_type_idx'),
            models.Index(fields=['priority'], name='rule_priority_idx'),
            models.Index(fields=['is_active'], name='rule_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.flag.name} - {self.rule_type} ({self.field})"
    
    def evaluate(self, context: dict) -> bool:
        """
        Evaluate the rule against the given context.
        
        Args:
            context: Context dictionary
            
        Returns:
            True if rule matches
        """
        if not self.is_active:
            return False
        
        field_value = context.get(self.field)
        
        if field_value is None:
            return False
        
        if self.operator == self.Operator.EQUALS:
            return field_value == self.value
        elif self.operator == self.Operator.NOT_EQUALS:
            return field_value != self.value
        elif self.operator == self.Operator.CONTAINS:
            return self.value in str(field_value)
        elif self.operator == self.Operator.NOT_CONTAINS:
            return self.value not in str(field_value)
        elif self.operator == self.Operator.STARTS_WITH:
            return str(field_value).startswith(str(self.value))
        elif self.operator == self.Operator.ENDS_WITH:
            return str(field_value).endswith(str(self.value))
        elif self.operator == self.Operator.GREATER_THAN:
            try:
                return float(field_value) > float(self.value)
            except (ValueError, TypeError):
                return False
        elif self.operator == self.Operator.LESS_THAN:
            try:
                return float(field_value) < float(self.value)
            except (ValueError, TypeError):
                return False
        elif self.operator == self.Operator.IN:
            return field_value in self.value if isinstance(self.value, list) else False
        elif self.operator == self.Operator.NOT_IN:
            return field_value not in self.value if isinstance(self.value, list) else False
        
        return False
