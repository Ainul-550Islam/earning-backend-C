"""
Click Fraud Signal Model for Offer Routing System

This module provides comprehensive click fraud detection and signaling,
including pattern recognition, anomaly detection, and automated blocking.
"""

import logging
from typing import Dict, Any, List
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class ClickFraudSignal(models.Model):
    """
    Model for storing click fraud signals and patterns.
    
    Tracks various fraud indicators including:
    - IP-based fraud
    - Device fingerprinting
    - Behavioral patterns
    - Time-based anomalies
    - Geographic inconsistencies
    """
    
    # Core fields
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fraud_signals',
        verbose_name=_('User'),
        help_text=_('User associated with this fraud signal')
    )
    
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        db_index=True,
        help_text=_('IP address associated with this fraud signal')
    )
    
    device_fingerprint = models.CharField(
        _('Device Fingerprint'),
        max_length=255,
        db_index=True,
        null=True,
        blank=True,
        help_text=_('Device fingerprint for fraud detection')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        null=True,
        blank=True,
        help_text=_('User agent string from the request')
    )
    
    # Fraud signal details
    signal_type = models.CharField(
        _('Signal Type'),
        max_length=50,
        choices=[
            ('high_click_rate', _('High Click Rate')),
            ('rapid_succession', _('Rapid Succession')),
            ('ip_concentration', _('IP Concentration')),
            ('device_concentration', _('Device Concentration')),
            ('geographic_anomaly', _('Geographic Anomaly')),
            ('time_pattern_anomaly', _('Time Pattern Anomaly')),
            ('conversion_anomaly', _('Conversion Anomaly')),
            ('bot_behavior', _('Bot Behavior')),
            ('proxy_detected', _('Proxy Detected')),
            ('vpn_detected', _('VPN Detected')),
            ('suspicious_timing', _('Suspicious Timing')),
            ('unusual_revenue', _('Unusual Revenue')),
            ('duplicate_clicks', _('Duplicate Clicks')),
            ('click_injection', _('Click Injection')),
            ('cookie_stuffing', _('Cookie Stuffing')),
        ],
        db_index=True,
        help_text=_('Type of fraud signal detected')
    )
    
    severity = models.CharField(
        _('Severity'),
        max_length=20,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('critical', _('Critical')),
        ],
        default='medium',
        db_index=True,
        help_text=_('Severity level of the fraud signal')
    )
    
    confidence_score = models.DecimalField(
        _('Confidence Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Confidence score of fraud detection (0-100)')
    )
    
    risk_score = models.DecimalField(
        _('Risk Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Overall risk score (0-100)')
    )
    
    # Context information
    offer_id = models.IntegerField(
        _('Offer ID'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Offer ID associated with this fraud signal')
    )
    
    route_id = models.IntegerField(
        _('Route ID'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Route ID associated with this fraud signal')
    )
    
    network_id = models.IntegerField(
        _('Network ID'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Network ID associated with this fraud signal')
    )
    
    # Geographic information
    country = models.CharField(
        _('Country'),
        max_length=2,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Country code (ISO 3166-1 alpha-2)')
    )
    
    region = models.CharField(
        _('Region'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Region or state')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('City name')
    )
    
    # Timing information
    click_timestamp = models.DateTimeField(
        _('Click Timestamp'),
        db_index=True,
        help_text=_('Timestamp when the click occurred')
    )
    
    session_id = models.CharField(
        _('Session ID'),
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Session identifier')
    )
    
    # Fraud detection details
    detection_method = models.CharField(
        _('Detection Method'),
        max_length=50,
        choices=[
            ('pattern_analysis', _('Pattern Analysis')),
            ('statistical_anomaly', _('Statistical Anomaly')),
            ('machine_learning', _('Machine Learning')),
            ('rule_based', _('Rule Based')),
            ('behavioral_analysis', _('Behavioral Analysis')),
            ('ip_reputation', _('IP Reputation')),
            ('device_analysis', _('Device Analysis')),
            ('time_series', _('Time Series Analysis')),
        ],
        default='pattern_analysis',
        help_text=_('Method used to detect the fraud signal')
    )
    
    detection_model = models.CharField(
        _('Detection Model'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Name of the detection model used')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata about the fraud signal')
    )
    
    raw_data = models.JSONField(
        _('Raw Data'),
        default=dict,
        blank=True,
        help_text=_('Raw data used for fraud detection')
    )
    
    # Action taken
    action_taken = models.CharField(
        _('Action Taken'),
        max_length=50,
        choices=[
            ('none', _('None')),
            ('warning', _('Warning')),
            ('temporary_block', _('Temporary Block')),
            ('permanent_block', _('Permanent Block')),
            ('user_suspension', _('User Suspension')),
            ('offer_removal', _('Offer Removal')),
            ('network_notification', _('Network Notification')),
            ('manual_review', _('Manual Review')),
        ],
        default='none',
        help_text=_('Action taken in response to this fraud signal')
    )
    
    action_timestamp = models.DateTimeField(
        _('Action Timestamp'),
        null=True,
        blank=True,
        help_text=_('Timestamp when action was taken')
    )
    
    # Resolution information
    is_resolved = models.BooleanField(
        _('Is Resolved'),
        default=False,
        db_index=True,
        help_text=_('Whether this fraud signal has been resolved')
    )
    
    resolution_method = models.CharField(
        _('Resolution Method'),
        max_length=50,
        choices=[
            ('automatic', _('Automatic')),
            ('manual_review', _('Manual Review')),
            ('false_positive', _('False Positive')),
            ('confirmed_fraud', _('Confirmed Fraud')),
            ('expired', _('Expired')),
        ],
        null=True,
        blank=True,
        help_text=_('Method used to resolve this fraud signal')
    )
    
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_fraud_signals',
        verbose_name=_('Resolved By'),
        help_text=_('User who resolved this fraud signal')
    )
    
    resolved_at = models.DateTimeField(
        _('Resolved At'),
        null=True,
        blank=True,
        help_text=_('Timestamp when this fraud signal was resolved')
    )
    
    resolution_notes = models.TextField(
        _('Resolution Notes'),
        null=True,
        blank=True,
        help_text=_('Notes about the resolution')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('Timestamp when this fraud signal was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('Timestamp when this fraud signal was last updated')
    )
    
    class Meta:
        db_table = 'offer_routing_click_fraud_signal'
        verbose_name = _('Click Fraud Signal')
        verbose_name_plural = _('Click Fraud Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at'], name='idx_user_created_at_1232'),
            models.Index(fields=['ip_address', 'created_at'], name='idx_ip_address_created_at_1233'),
            models.Index(fields=['device_fingerprint', 'created_at'], name='idx_device_fingerprint_cre_7b0'),
            models.Index(fields=['signal_type', 'severity'], name='idx_signal_type_severity_1235'),
            models.Index(fields=['risk_score'], name='idx_risk_score_1236'),
            models.Index(fields=['is_resolved', 'created_at'], name='idx_is_resolved_created_at_12f'),
        ]
    
    def __str__(self):
        return f"Fraud Signal: {self.signal_type} - {self.severity} - {self.ip_address}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate confidence score
        if self.confidence_score < 0 or self.confidence_score > 100:
            raise ValidationError(_('Confidence score must be between 0 and 100'))
        
        # Validate risk score
        if self.risk_score < 0 or self.risk_score > 100:
            raise ValidationError(_('Risk score must be between 0 and 100'))
        
        # Validate IP address format
        if self.ip_address:
            import ipaddress
            try:
                ipaddress.ip_address(self.ip_address)
            except ValueError:
                raise ValidationError(_('Invalid IP address format'))
        
        # Validate country code
        if self.country and len(self.country) != 2:
            raise ValidationError(_('Country code must be 2 characters'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Set click timestamp if not provided
        if not self.click_timestamp:
            self.click_timestamp = timezone.now()
        
        # Set action timestamp if action was taken
        if self.action_taken != 'none' and not self.action_timestamp:
            self.action_timestamp = timezone.now()
        
        # Set resolved timestamp if resolved
        if self.is_resolved and not self.resolved_at:
            self.resolved_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk fraud signal."""
        return (
            self.severity in ['high', 'critical'] or
            self.risk_score >= 70 or
            self.confidence_score >= 80
        )
    
    @property
    def requires_immediate_action(self) -> bool:
        """Check if this signal requires immediate action."""
        return (
            self.severity == 'critical' or
            self.risk_score >= 90 or
            self.signal_type in ['bot_behavior', 'click_injection', 'cookie_stuffing']
        )
    
    @property
    def age_hours(self) -> int:
        """Get age of this fraud signal in hours."""
        if self.created_at:
            return int((timezone.now() - self.created_at).total_seconds() / 3600)
        return 0
    
    @property
    def is_stale(self) -> bool:
        """Check if this fraud signal is stale (older than 30 days)."""
        return self.age_hours > 720  # 30 days
    
    def get_related_signals(self, hours: int = 24) -> models.QuerySet:
        """Get related fraud signals within specified hours."""
        cutoff_time = self.created_at - timezone.timedelta(hours=hours)
        
        return ClickFraudSignal.objects.filter(
            models.Q(user=self.user) |
            models.Q(ip_address=self.ip_address) |
            models.Q(device_fingerprint=self.device_fingerprint),
            created_at__gte=cutoff_time,
            created_at__lte=self.created_at + timezone.timedelta(hours=hours)
        ).exclude(id=self.id)
    
    def get_signal_trend(self, hours: int = 24) -> Dict[str, any]:
        """Get trend analysis for this signal type."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        signals = ClickFraudSignal.objects.filter(
            signal_type=self.signal_type,
            created_at__gte=cutoff_time
        ).order_by('created_at')
        
        # Group by hour
        hourly_counts = {}
        for signal in signals:
            hour = signal.created_at.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        return {
            'total_signals': signals.count(),
            'hourly_distribution': hourly_counts,
            'peak_hour': max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else None,
            'average_per_hour': signals.count() / 24 if signals.count() > 0 else 0
        }
    
    def escalate_if_needed(self):
        """Escalate signal if conditions are met."""
        if self.requires_immediate_action and self.action_taken == 'none':
            # Auto-escalate critical signals
            self.action_taken = 'manual_review'
            self.save()
            
            # Log escalation
            logger.warning(f"Auto-escalated fraud signal {self.id} - {self.signal_type}")
    
    @classmethod
    def get_active_signals(cls, hours: int = 24) -> models.QuerySet:
        """Get active fraud signals within specified hours."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        return cls.objects.filter(
            created_at__gte=cutoff_time,
            is_resolved=False
        ).order_by('-risk_score', '-created_at')
    
    @classmethod
    def get_high_risk_signals(cls, hours: int = 24) -> models.QuerySet:
        """Get high-risk fraud signals within specified hours."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        return cls.objects.filter(
            created_at__gte=cutoff_time,
            is_resolved=False,
            risk_score__gte=70
        ).order_by('-risk_score', '-created_at')
    
    @classmethod
    def get_ip_based_signals(cls, ip_address: str, hours: int = 24) -> models.QuerySet:
        """Get fraud signals for specific IP address."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        return cls.objects.filter(
            ip_address=ip_address,
            created_at__gte=cutoff_time
        ).order_by('-created_at')
    
    @classmethod
    def get_device_based_signals(cls, device_fingerprint: str, hours: int = 24) -> models.QuerySet:
        """Get fraud signals for specific device fingerprint."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        return cls.objects.filter(
            device_fingerprint=device_fingerprint,
            created_at__gte=cutoff_time
        ).order_by('-created_at')
    
    @classmethod
    def get_user_based_signals(cls, user_id: int, hours: int = 24) -> models.QuerySet:
        """Get fraud signals for specific user."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        return cls.objects.filter(
            user_id=user_id,
            created_at__gte=cutoff_time
        ).order_by('-created_at')
    
    @classmethod
    def cleanup_old_signals(cls, days: int = 30):
        """Clean up old resolved fraud signals."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        deleted_count = cls.objects.filter(
            is_resolved=True,
            resolved_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old fraud signals")
        
        return deleted_count
    
    @classmethod
    def get_fraud_statistics(cls, hours: int = 24) -> Dict[str, any]:
        """Get fraud signal statistics."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        
        signals = cls.objects.filter(created_at__gte=cutoff_time)
        
        stats = {
            'total_signals': signals.count(),
            'unresolved_signals': signals.filter(is_resolved=False).count(),
            'high_risk_signals': signals.filter(risk_score__gte=70).count(),
            'critical_signals': signals.filter(severity='critical').count(),
            'signals_by_type': {},
            'signals_by_severity': {},
            'signals_by_detection_method': {},
            'average_risk_score': signals.aggregate(
                avg_risk=models.Avg('risk_score')
            )['avg_risk'] or 0,
            'average_confidence_score': signals.aggregate(
                avg_confidence=models.Avg('confidence_score')
            )['avg_confidence'] or 0,
        }
        
        # Group by signal type
        for signal_type, _ in cls._meta.get_field('signal_type').choices:
            count = signals.filter(signal_type=signal_type).count()
            if count > 0:
                stats['signals_by_type'][signal_type] = count
        
        # Group by severity
        for severity, _ in cls._meta.get_field('severity').choices:
            count = signals.filter(severity=severity).count()
            if count > 0:
                stats['signals_by_severity'][severity] = count
        
        # Group by detection method
        for method, _ in cls._meta.get_field('detection_method').choices:
            count = signals.filter(detection_method=method).count()
            if count > 0:
                stats['signals_by_detection_method'][method] = count
        
        return stats


class FraudPattern(models.Model):
    """
    Model for storing known fraud patterns.
    
    Stores patterns that have been identified as fraudulent
    and can be used for pattern matching.
    """
    
    name = models.CharField(
        _('Pattern Name'),
        max_length=100,
        unique=True,
        help_text=_('Name of the fraud pattern')
    )
    
    description = models.TextField(
        _('Description'),
        help_text=_('Description of the fraud pattern')
    )
    
    pattern_type = models.CharField(
        _('Pattern Type'),
        max_length=50,
        choices=[
            ('ip_pattern', _('IP Pattern')),
            ('device_pattern', _('Device Pattern')),
            ('time_pattern', _('Time Pattern')),
            ('behavioral_pattern', _('Behavioral Pattern')),
            ('geographic_pattern', _('Geographic Pattern')),
            ('conversion_pattern', _('Conversion Pattern')),
        ],
        help_text=_('Type of fraud pattern')
    )
    
    pattern_data = models.JSONField(
        _('Pattern Data'),
        default=dict,
        help_text=_('Pattern matching data')
    )
    
    detection_rules = models.JSONField(
        _('Detection Rules'),
        default=dict,
        help_text=_('Rules for detecting this pattern')
    )
    
    confidence_threshold = models.DecimalField(
        _('Confidence Threshold'),
        max_digits=5,
        decimal_places=2,
        default=80.00,
        help_text=_('Minimum confidence threshold for pattern matching')
    )
    
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this pattern is active')
    )
    
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('Timestamp when this pattern was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('Timestamp when this pattern was last updated')
    )
    
    class Meta:
        db_table = 'offer_routing_fraud_pattern'
        verbose_name = _('Fraud Pattern')
        verbose_name_plural = _('Fraud Patterns')
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def match_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Check if signal data matches this pattern."""
        try:
            # Implement pattern matching logic
            # This would depend on the pattern type and detection rules
            
            if self.pattern_type == 'ip_pattern':
                return self._match_ip_pattern(signal_data)
            elif self.pattern_type == 'device_pattern':
                return self._match_device_pattern(signal_data)
            elif self.pattern_type == 'time_pattern':
                return self._match_time_pattern(signal_data)
            elif self.pattern_type == 'behavioral_pattern':
                return self._match_behavioral_pattern(signal_data)
            elif self.pattern_type == 'geographic_pattern':
                return self._match_geographic_pattern(signal_data)
            elif self.pattern_type == 'conversion_pattern':
                return self._match_conversion_pattern(signal_data)
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching pattern {self.name}: {e}")
            return False
    
    def _match_ip_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Match IP-based fraud pattern."""
        # Implement IP pattern matching
        return False
    
    def _match_device_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Match device-based fraud pattern."""
        # Implement device pattern matching
        return False
    
    def _match_time_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Match time-based fraud pattern."""
        # Implement time pattern matching
        return False
    
    def _match_behavioral_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Match behavioral fraud pattern."""
        # Implement behavioral pattern matching
        return False
    
    def _match_geographic_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Match geographic fraud pattern."""
        # Implement geographic pattern matching
        return False
    
    def _match_conversion_pattern(self, signal_data: Dict[str, any]) -> bool:
        """Match conversion-based fraud pattern."""
        # Implement conversion pattern matching
        return False


# Signal handlers for fraud detection
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=ClickFraudSignal)
def fraud_signal_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for fraud signals."""
    if created:
        # Log new fraud signal
        logger.info(f"New fraud signal created: {instance.signal_type} - {instance.severity}")
        
        # Auto-escalate if needed
        instance.escalate_if_needed()
        
        # Trigger fraud detection tasks
        from ..tasks.fraud import process_fraud_signal
        process_fraud_signal.delay(instance.id)

@receiver(post_delete, sender=ClickFraudSignal)
def fraud_signal_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for fraud signals."""
    logger.info(f"Fraud signal deleted: {instance.signal_type} - {instance.ip_address}")
