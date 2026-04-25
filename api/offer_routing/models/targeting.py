"""
Targeting Models for Offer Routing System

This module contains models for geographic, device, user segment,
time-based, and behavioral targeting rules.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..choices import (
    UserSegmentType, DeviceType, OSType, BrowserType,
    EventType
)
from ..constants import DEFAULT_BEHAVIOR_WINDOW_DAYS

User = get_user_model()


class GeoRouteRule(models.Model):
    """
    Geographic targeting rules for offer routing.
    
    Defines which users see offers based on their location
    (country, region, city).
    """
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='geo_rules',
        verbose_name=_('Route')
    )
    country = models.CharField(
        _('Country Code'),
        max_length=2,
        help_text=_('ISO 3166-1 alpha-2 country code')
    )
    region = models.CharField(
        _('Region'),
        max_length=100,
        blank=True,
        help_text=_('Geographic region (state, province, etc.)')
    )
    city = models.CharField(
        _('City'),
        max_length=100,
        blank=True,
        help_text=_('City name')
    )
    is_include = models.BooleanField(
        _('Is Include'),
        default=True,
        help_text=_('True to include, False to exclude users in this location')
    )
    priority = models.IntegerField(
        _('Priority'),
        default=0,
        help_text=_('Higher priority rules are evaluated first')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_geo_rules'
        verbose_name = _('Geographic Route Rule')
        verbose_name_plural = _('Geographic Route Rules')
        ordering = ['-priority', 'country', 'region', 'city']
        indexes = [
            models.Index(fields=['route', 'country', 'is_include'], name='idx_route_country_is_inclu_5cd'),
            models.Index(fields=['route', 'priority'], name='idx_route_priority_1332'),
            models.Index(fields=['created_at'], name='idx_created_at_1333'),
        ]
    
    def __str__(self):
        location_parts = []
        if self.country:
            location_parts.append(self.country)
        if self.region:
            location_parts.append(self.region)
        if self.city:
            location_parts.append(self.city)
        
        location = ', '.join(location_parts) if location_parts else 'Global'
        return f"{self.route.name} - {location} ({'Include' if self.is_include else 'Exclude'})"
    
    def clean(self):
        """Validate model data."""
        if self.country and len(self.country) != 2:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Country code must be exactly 2 characters'))
        
        if self.priority < 0 or self.priority > 100:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Priority must be between 0 and 100'))


class DeviceRouteRule(models.Model):
    """
    Device-based targeting rules for offer routing.
    
    Defines which users see offers based on their device type,
    operating system, and browser.
    """
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='device_rules',
        verbose_name=_('Route')
    )
    device_type = models.CharField(
        _('Device Type'),
        max_length=20,
        choices=DeviceType.CHOICES,
        help_text=_('Target device type (mobile, desktop, tablet, etc.)')
    )
    os_type = models.CharField(
        _('OS Type'),
        max_length=20,
        choices=OSType.CHOICES,
        blank=True,
        help_text=_('Target operating system')
    )
    browser = models.CharField(
        _('Browser'),
        max_length=20,
        choices=BrowserType.CHOICES,
        blank=True,
        help_text=_('Target browser type')
    )
    is_include = models.BooleanField(
        _('Is Include'),
        default=True,
        help_text=_('True to include, False to exclude users with this device')
    )
    priority = models.IntegerField(
        _('Priority'),
        default=0,
        help_text=_('Higher priority rules are evaluated first')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_device_rules'
        verbose_name = _('Device Route Rule')
        verbose_name_plural = _('Device Route Rules')
        ordering = ['-priority', 'device_type', 'os_type', 'browser']
        indexes = [
            models.Index(fields=['route', 'device_type', 'is_include'], name='idx_route_device_type_is_i_363'),
            models.Index(fields=['route', 'priority'], name='idx_route_priority_1335'),
            models.Index(fields=['created_at'], name='idx_created_at_1336'),
        ]
    
    def __str__(self):
        device_parts = []
        if self.device_type:
            device_parts.append(self.device_type)
        if self.os_type:
            device_parts.append(self.os_type)
        if self.browser:
            device_parts.append(self.browser)
        
        device = ' - '.join(device_parts) if device_parts else 'All Devices'
        return f"{self.route.name} - {device} ({'Include' if self.is_include else 'Exclude'})"


class UserSegmentRule(models.Model):
    """
    User segment targeting rules for offer routing.
    
    Defines which users see offers based on their segment
    (tier, new user, active user, churned user, etc.).
    """
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='segment_rules',
        verbose_name=_('Route')
    )
    segment_type = models.CharField(
        _('Segment Type'),
        max_length=20,
        choices=UserSegmentType.CHOICES,
        help_text=_('Type of user segment to target')
    )
    value = models.CharField(
        _('Segment Value'),
        max_length=100,
        help_text=_('Value that defines this segment (e.g., tier name, "true" for boolean)')
    )
    operator = models.CharField(
        _('Operator'),
        max_length=20,
        choices=[
            ('equals', 'Equals'),
            ('not_equals', 'Not Equals'),
            ('in', 'In List'),
            ('not_in', 'Not In List'),
            ('contains', 'Contains'),
            ('not_contains', 'Does Not Contain'),
        ],
        default='equals',
        help_text=_('Comparison operator for segment evaluation')
    )
    priority = models.IntegerField(
        _('Priority'),
        default=0,
        help_text=_('Higher priority rules are evaluated first')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_segment_rules'
        verbose_name = _('User Segment Rule')
        verbose_name_plural = _('User Segment Rules')
        ordering = ['-priority', 'segment_type', 'value']
        indexes = [
            models.Index(fields=['route', 'segment_type', 'value'], name='idx_route_segment_type_val_29f'),
            models.Index(fields=['route', 'priority'], name='idx_route_priority_1338'),
            models.Index(fields=['created_at'], name='idx_created_at_1339'),
        ]
    
    def __str__(self):
        return f"{self.route.name} - {self.segment_type} {self.operator} {self.value}"


class TimeRouteRule(models.Model):
    """
    Time-based targeting rules for offer routing.
    
    Defines which users see offers based on time of day,
    day of week, and timezone.
    """
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='time_rules',
        verbose_name=_('Route')
    )
    day_of_week = models.JSONField(
        _('Day of Week'),
        help_text=_('Days of week when rule applies (0=Sunday, 1=Monday, etc.)')
    )
    hour_from = models.IntegerField(
        _('Hour From'),
        help_text=_('Start hour when rule applies (0-23)')
    )
    hour_to = models.IntegerField(
        _('Hour To'),
        help_text=_('End hour when rule applies (0-23)')
    )
    timezone = models.CharField(
        _('Timezone'),
        max_length=50,
        default='UTC',
        help_text=_('Timezone for time calculations')
    )
    priority = models.IntegerField(
        _('Priority'),
        default=0,
        help_text=_('Higher priority rules are evaluated first')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_time_rules'
        verbose_name = _('Time Route Rule')
        verbose_name_plural = _('Time Route Rules')
        ordering = ['-priority', 'hour_from', 'hour_to']
        indexes = [
            models.Index(fields=['route', 'hour_from', 'hour_to'], name='idx_route_hour_from_hour_t_f61'),
            models.Index(fields=['route', 'priority'], name='idx_route_priority_1341'),
            models.Index(fields=['created_at'], name='idx_created_at_1342'),
        ]
    
    def __str__(self):
        return f"{self.route.name} - {self.hour_from}:00 to {self.hour_to}:59 {self.timezone}"
    
    def clean(self):
        """Validate model data."""
        if self.hour_from < 0 or self.hour_from > 23:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Hour from must be between 0 and 23'))
        
        if self.hour_to < 0 or self.hour_to > 23:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Hour to must be between 0 and 23'))
        
        if self.hour_from > self.hour_to:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Hour from must be less than or equal to hour to'))
    
    def matches_time(self, current_hour, current_day_of_week):
        """Check if current time matches this rule."""
        # Check day of week
        if self.day_of_week:
            if isinstance(self.day_of_week, list):
                if current_day_of_week not in self.day_of_week:
                    return False
            else:
                return current_day_of_week == self.day_of_week
        
        # Check hour range
        if self.hour_from <= current_hour <= self.hour_to:
            return True
        
        return False


class BehaviorRouteRule(models.Model):
    """
    Behavioral targeting rules for offer routing.
    
    Defines which users see offers based on their past behavior
    (events, actions, engagement patterns).
    """
    
    route = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='behavior_rules',
        verbose_name=_('Route')
    )
    event_type = models.CharField(
        _('Event Type'),
        max_length=20,
        choices=EventType.CHOICES,
        help_text=_('Type of user event to track')
    )
    min_count = models.IntegerField(
        _('Minimum Count'),
        default=1,
        help_text=_('Minimum number of events to trigger rule')
    )
    window_days = models.IntegerField(
        _('Window Days'),
        default=DEFAULT_BEHAVIOR_WINDOW_DAYS,
        help_text=_('Time window in days to look back for events')
    )
    operator = models.CharField(
        _('Operator'),
        max_length=20,
        choices=[
            ('equals', 'Equals'),
            ('greater_than', 'Greater Than'),
            ('less_than', 'Less Than'),
            ('greater_equal', 'Greater or Equal'),
            ('less_equal', 'Less or Equal'),
        ],
        default='greater_than',
        help_text=_('Comparison operator for event count')
    )
    priority = models.IntegerField(
        _('Priority'),
        default=0,
        help_text=_('Higher priority rules are evaluated first')
    )
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'offer_routing_behavior_rules'
        verbose_name = _('Behavior Route Rule')
        verbose_name_plural = _('Behavior Route Rules')
        ordering = ['-priority', 'event_type', 'min_count']
        indexes = [
            models.Index(fields=['route', 'event_type', 'min_count'], name='idx_route_event_type_min_c_349'),
            models.Index(fields=['route', 'priority'], name='idx_route_priority_1344'),
            models.Index(fields=['created_at'], name='idx_created_at_1345'),
        ]
    
    def __str__(self):
        return f"{self.route.name} - {self.event_type} {self.operator} {self.min_count} (last {self.window_days} days)"
    
    def clean(self):
        """Validate model data."""
        if self.min_count < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Minimum count must be at least 1'))
        
        if self.window_days < 1 or self.window_days > 365:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Window days must be between 1 and 365'))
    
    def matches_behavior(self, user_events):
        """Check if user behavior matches this rule."""
        cutoff_date = timezone.now() - timezone.timedelta(days=self.window_days)
        
        # Filter events by type and date range
        relevant_events = [
            event for event in user_events
            if event.get('event_type') == self.event_type and
            event.get('created_at') >= cutoff_date
        ]
        
        if not relevant_events:
            return False
        
        # Count events
        event_count = len(relevant_events)
        
        # Apply operator
        if self.operator == 'equals':
            return event_count == self.min_count
        elif self.operator == 'greater_than':
            return event_count > self.min_count
        elif self.operator == 'less_than':
            return event_count < self.min_count
        elif self.operator == 'greater_equal':
            return event_count >= self.min_count
        elif self.operator == 'less_equal':
            return event_count <= self.min_count
        
        return False


class TargetingRuleManager(models.Manager):
    """
    Custom manager for targeting rules with utility methods.
    """
    
    def get_active_rules(self, route_id=None):
        """Get all active targeting rules for a route."""
        queryset = self.filter(is_active=True)
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        return queryset.order_by('-priority')
    
    def get_rules_by_type(self, rule_type, route_id=None):
        """Get rules by type (geo, device, segment, time, behavior)."""
        rule_models = {
            'geo': GeoRouteRule,
            'device': DeviceRouteRule,
            'segment': UserSegmentRule,
            'time': TimeRouteRule,
            'behavior': BehaviorRouteRule,
        }
        
        model_class = rule_models.get(rule_type)
        if not model_class:
            return self.none()
        
        queryset = self.filter(is_active=True)
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        
        return queryset.order_by('-priority')
    
    def evaluate_user_for_route(self, user, route):
        """Evaluate if user matches all targeting rules for a route."""
        if not route or not user:
            return False
        
        # Check each type of targeting rule
        geo_match = self._check_geo_rules(user, route)
        device_match = self._check_device_rules(user, route)
        segment_match = self._check_segment_rules(user, route)
        time_match = self._check_time_rules(user, route)
        behavior_match = self._check_behavior_rules(user, route)
        
        # User must match at least one rule type to be targeted
        return any([geo_match, device_match, segment_match, time_match, behavior_match])
    
    def _check_geo_rules(self, user, route):
        """Check if user matches geographic rules."""
        geo_rules = route.geo_rules.filter(is_active=True)
        
        for rule in geo_rules:
            if rule.matches_user(user):
                return rule.is_include
        
        return False  # No matching rules
    
    def _check_device_rules(self, user, route):
        """Check if user matches device rules."""
        device_rules = route.device_rules.filter(is_active=True)
        
        for rule in device_rules:
            if rule.matches_user(user):
                return rule.is_include
        
        return False  # No matching rules
    
    def _check_segment_rules(self, user, route):
        """Check if user matches segment rules."""
        segment_rules = route.segment_rules.filter(is_active=True)
        
        for rule in segment_rules:
            if rule.matches_user(user):
                return True  # Segment rules are always inclusion
        
        return False  # No matching rules
    
    def _check_time_rules(self, user, route):
        """Check if user matches time rules."""
        time_rules = route.time_rules.filter(is_active=True)
        
        for rule in time_rules:
            if rule.matches_user(user):
                return True  # Time rules are always inclusion
        
        return False  # No matching rules
    
    def _check_behavior_rules(self, user, route):
        """Check if user matches behavioral rules."""
        behavior_rules = route.behavior_rules.filter(is_active=True)
        
        for rule in behavior_rules:
            if rule.matches_user(user):
                return True  # Behavior rules are always inclusion
        
        return False  # No matching rules


# Add custom manager to models
GeoRouteRule.add_manager_class = TargetingRuleManager()
DeviceRouteRule.add_manager_class = TargetingRuleManager()
UserSegmentRule.add_manager_class = TargetingRuleManager()
TimeRouteRule.add_manager_class = TargetingRuleManager()
BehaviorRouteRule.add_manager_class = TargetingRuleManager()
