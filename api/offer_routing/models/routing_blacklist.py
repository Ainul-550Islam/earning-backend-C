"""
Routing Blacklist Model for Offer Routing System

This module provides comprehensive blacklist management,
including IP blocking, user suspension, and offer filtering.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingBlacklist(models.Model):
    """
    Model for managing routing blacklists.
    
    Handles various blacklist types including:
    - IP address blocking
    - User suspension
    - Offer filtering
    - Network restrictions
    - Geographic blocking
    - Device blocking
    """
    
    # Core identification
    blacklist_type = models.CharField(
        _('Blacklist Type'),
        max_length=50,
        choices=[
            ('ip_address', _('IP Address')),
            ('user_id', _('User ID')),
            ('email_domain', _('Email Domain')),
            ('device_fingerprint', _('Device Fingerprint')),
            ('offer_id', _('Offer ID')),
            ('network_id', _('Network ID')),
            ('country', _('Country')),
            ('region', _('Region')),
            ('user_agent', _('User Agent')),
            ('referer', _('Referer')),
            ('subdomain', _('Subdomain')),
            ('custom_rule', _('Custom Rule')),
        ],
        db_index=True,
        help_text=_('Type of blacklist entry')
    )
    
    # Target identification
    target_value = models.CharField(
        _('Target Value'),
        max_length=500,
        db_index=True,
        help_text=_('Value to be blacklisted (IP, user ID, domain, etc.)')
    )
    
    target_pattern = models.CharField(
        _('Target Pattern'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('Pattern for matching (regex, wildcard, etc.)')
    )
    
    # Blacklist details
    reason = models.CharField(
        _('Reason'),
        max_length=200,
        choices=[
            ('fraud', _('Fraud')),
            ('spam', _('Spam')),
            ('abuse', _('Abuse')),
            ('violation', _('Policy Violation')),
            ('security', _('Security Risk')),
            ('compliance', _('Compliance')),
            ('quality', _('Quality Issues')),
            ('performance', _('Performance Issues')),
            ('manual', _('Manual Block')),
            ('automatic', _('Automatic Block')),
            ('temporary', _('Temporary Block')),
            ('investigation', _('Under Investigation')),
        ],
        help_text=_('Reason for blacklisting')
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
        help_text=_('Severity level of the blacklist entry')
    )
    
    # Blocking configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this blacklist entry is active')
    )
    
    is_permanent = models.BooleanField(
        _('Is Permanent'),
        default=False,
        help_text=_('Whether this blacklist entry is permanent')
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this blacklist entry expires')
    )
    
    # Action configuration
    action = models.CharField(
        _('Action'),
        max_length=50,
        choices=[
            ('block', _('Block')),
            ('redirect', _('Redirect')),
            ('warn', _('Warn')),
            ('log', _('Log Only')),
            ('throttle', _('Throttle')),
            ('quarantine', _('Quarantine')),
            ('review', _('Manual Review')),
        ],
        default='block',
        help_text=_('Action to take when blacklist entry matches')
    )
    
    redirect_url = models.URLField(
        _('Redirect URL'),
        null=True,
        blank=True,
        help_text=_('URL to redirect to (for redirect action)')
    )
    
    throttle_rate = models.CharField(
        _('Throttle Rate'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Throttle rate (e.g., "10/min", "100/hour")')
    )
    
    # Scope configuration
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='blacklist_entries',
        null=True,
        blank=True,
        verbose_name=_('tenants.Tenant'),
        help_text=_('Tenant this blacklist entry applies to')
    )
    
    applies_to_all_tenants = models.BooleanField(
        _('Applies to All Tenants'),
        default=False,
        help_text=_('Whether this blacklist entry applies to all tenants')
    )
    
    # Geographic scope
    countries = models.JSONField(
        _('Countries'),
        default=list,
        blank=True,
        help_text=_('List of country codes this applies to')
    )
    
    regions = models.JSONField(
        _('Regions'),
        default=list,
        blank=True,
        help_text=_('List of regions this applies to')
    )
    
    # Time-based scope
    active_hours = models.JSONField(
        _('Active Hours'),
        default=list,
        blank=True,
        help_text=_('Hours when this blacklist is active (0-23)')
    )
    
    active_days = models.JSONField(
        _('Active Days'),
        default=list,
        blank=True,
        help_text=_('Days when this blacklist is active (0-6, 0=Monday)')
    )
    
    # Matching configuration
    match_type = models.CharField(
        _('Match Type'),
        max_length=50,
        choices=[
            ('exact', _('Exact Match')),
            ('contains', _('Contains')),
            ('starts_with', _('Starts With')),
            ('ends_with', _('Ends With')),
            ('regex', _('Regular Expression')),
            ('wildcard', _('Wildcard')),
            ('cidr', _('CIDR Range')),
            ('range', _('Range')),
        ],
        default='exact',
        help_text=_('How to match the target value')
    )
    
    case_sensitive = models.BooleanField(
        _('Case Sensitive'),
        default=True,
        help_text=_('Whether matching is case sensitive')
    )
    
    negated = models.BooleanField(
        _('Negated'),
        default=False,
        help_text=_('Whether to negate the match (whitelist)')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata about the blacklist entry')
    )
    
    notes = models.TextField(
        _('Notes'),
        null=True,
        blank=True,
        help_text=_('Additional notes about the blacklist entry')
    )
    
    # Statistics
    hit_count = models.IntegerField(
        _('Hit Count'),
        default=0,
        help_text=_('Number of times this blacklist entry has been matched')
    )
    
    last_hit_at = models.DateTimeField(
        _('Last Hit At'),
        null=True,
        blank=True,
        help_text=_('Last time this blacklist entry was matched')
    )
    
    # Audit information
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_blacklist_entries',
        verbose_name=_('Created By'),
        help_text=_('User who created this blacklist entry')
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_blacklist_entries',
        verbose_name=_('Approved By'),
        help_text=_('User who approved this blacklist entry')
    )
    
    approved_at = models.DateTimeField(
        _('Approved At'),
        null=True,
        blank=True,
        help_text=_('When this blacklist entry was approved')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('Timestamp when this blacklist entry was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('Timestamp when this blacklist entry was last updated')
    )
    
    class Meta:
        db_table = 'offer_routing_blacklist'
        verbose_name = _('Routing Blacklist')
        verbose_name_plural = _('Routing Blacklists')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['blacklist_type', 'target_value'], name='idx_blacklist_type_target__d28'),
            models.Index(fields=['is_active', 'expires_at'], name='idx_is_active_expires_at_1301'),
            models.Index(fields=['severity', 'created_at'], name='idx_severity_created_at_1302'),
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1303'),
            models.Index(fields=['applies_to_all_tenants', 'is_active'], name='idx_applies_to_all_tenants_e5f'),
            models.Index(fields=['hit_count', 'last_hit_at'], name='idx_hit_count_last_hit_at_1305'),
        ]
        unique_together = [
            ['blacklist_type', 'target_value', 'tenant'],
        ]
    
    def __str__(self):
        return f"Blacklist: {self.blacklist_type} - {self.target_value} ({self.severity})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate target value
        if not self.target_value.strip():
            raise ValidationError(_('Target value cannot be empty'))
        
        # Validate expiration
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError(_('Expiration date must be in the future'))
        
        # Validate redirect URL for redirect action
        if self.action == 'redirect' and not self.redirect_url:
            raise ValidationError(_('Redirect URL is required for redirect action'))
        
        # Validate throttle rate for throttle action
        if self.action == 'throttle' and not self.throttle_rate:
            raise ValidationError(_('Throttle rate is required for throttle action'))
        
        # Validate IP address format
        if self.blacklist_type == 'ip_address':
            self._validate_ip_address()
        
        # Validate regex pattern
        if self.match_type == 'regex':
            self._validate_regex_pattern()
    
    def _validate_ip_address(self):
        """Validate IP address format."""
        import ipaddress
        
        try:
            if self.match_type == 'cidr':
                ipaddress.ip_network(self.target_value)
            else:
                ipaddress.ip_address(self.target_value)
        except ValueError:
            raise ValidationError(_('Invalid IP address format'))
    
    def _validate_regex_pattern(self):
        """Validate regex pattern."""
        import re
        
        try:
            re.compile(self.target_value)
        except re.error:
            raise ValidationError(_('Invalid regular expression pattern'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Set expiration for non-permanent entries
        if not self.is_permanent and not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=30)  # Default 30 days
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self) -> bool:
        """Check if blacklist entry is expired."""
        if self.is_permanent:
            return False
        
        if self.expires_at:
            return timezone.now() > self.expires_at
        
        return False
    
    @property
    def is_currently_active(self) -> bool:
        """Check if blacklist entry is currently active."""
        if not self.is_active or self.is_expired:
            return False
        
        # Check time-based restrictions
        if self.active_hours and timezone.now().hour not in self.active_hours:
            return False
        
        if self.active_days and timezone.now().weekday() not in self.active_days:
            return False
        
        return True
    
    @property
    def age_days(self) -> int:
        """Get age of blacklist entry in days."""
        if self.created_at:
            return (timezone.now() - self.created_at).days
        return 0
    
    def matches(self, value: str, context: dict = None) -> bool:
        """Check if value matches this blacklist entry."""
        if not self.is_currently_active:
            return False
        
        try:
            # Apply case sensitivity
            target = self.target_value
            check_value = value
            
            if not self.case_sensitive:
                target = target.lower()
                check_value = check_value.lower()
            
            # Apply matching logic
            if self.match_type == 'exact':
                match = check_value == target
            elif self.match_type == 'contains':
                match = target in check_value
            elif self.match_type == 'starts_with':
                match = check_value.startswith(target)
            elif self.match_type == 'ends_with':
                match = check_value.endswith(target)
            elif self.match_type == 'regex':
                import re
                match = bool(re.search(target, check_value))
            elif self.match_type == 'wildcard':
                match = self._wildcard_match(target, check_value)
            elif self.match_type == 'cidr':
                match = self._cidr_match(target, check_value)
            elif self.match_type == 'range':
                match = self._range_match(target, check_value)
            else:
                match = False
            
            # Apply negation
            if self.negated:
                match = not match
            
            # Update hit count if match
            if match:
                self.hit_count += 1
                self.last_hit_at = timezone.now()
                self.save(update_fields=['hit_count', 'last_hit_at'])
            
            return match
            
        except Exception as e:
            logger.error(f"Error matching blacklist entry {self.id}: {e}")
            return False
    
    def _wildcard_match(self, pattern: str, value: str) -> bool:
        """Match using wildcard pattern."""
        import fnmatch
        return fnmatch.fnmatch(value, pattern)
    
    def _cidr_match(self, network: str, ip: str) -> bool:
        """Match using CIDR network."""
        import ipaddress
        try:
            network_obj = ipaddress.ip_network(network)
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj in network_obj
        except ValueError:
            return False
    
    def _range_match(self, range_str: str, value: str) -> bool:
        """Match using range."""
        try:
            # Parse range (e.g., "100-200" or "a-z")
            if '-' in range_str:
                start, end = range_str.split('-', 1)
                
                # Numeric range
                if start.isdigit() and end.isdigit():
                    num_value = int(value) if value.isdigit() else 0
                    return start <= num_value <= end
                
                # Character range
                return start <= value <= end
            
            return False
            
        except Exception:
            return False
    
    def record_hit(self, request_data: dict = None):
        """Record a hit for this blacklist entry."""
        self.hit_count += 1
        self.last_hit_at = timezone.now()
        self.save(update_fields=['hit_count', 'last_hit_at'])
        
        # Log hit
        logger.warning(f"Blacklist hit: {self.blacklist_type} - {self.target_value}")
        
        # Store hit details if provided
        if request_data:
            BlacklistHit.objects.create(
                blacklist_entry=self,
                request_data=request_data,
                hit_time=timezone.now()
            )
    
    @classmethod
    def check_blacklist(cls, blacklist_type: str, value: str, tenant_id: int = None, context: dict = None) -> dict:
        """Check if value matches any blacklist entries."""
        try:
            # Get active blacklist entries
            entries = cls.objects.filter(
                blacklist_type=blacklist_type,
                is_active=True
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            )
            
            # Filter by tenant
            if tenant_id:
                entries = entries.filter(
                    models.Q(tenant_id=tenant_id) | models.Q(applies_to_all_tenants=True)
                )
            else:
                entries = entries.filter(applies_to_all_tenants=True)
            
            # Check for matches
            for entry in entries:
                if entry.matches(value, context):
                    return {
                        'blocked': True,
                        'entry': entry,
                        'action': entry.action,
                        'severity': entry.severity,
                        'reason': entry.reason,
                        'redirect_url': entry.redirect_url,
                        'throttle_rate': entry.throttle_rate,
                    }
            
            return {'blocked': False}
            
        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return {'blocked': False}
    
    @classmethod
    def get_active_entries(cls, blacklist_type: str = None, tenant_id: int = None) -> models.QuerySet:
        """Get active blacklist entries."""
        entries = cls.objects.filter(
            is_active=True
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )
        
        if blacklist_type:
            entries = entries.filter(blacklist_type=blacklist_type)
        
        if tenant_id:
            entries = entries.filter(
                models.Q(tenant_id=tenant_id) | models.Q(applies_to_all_tenants=True)
            )
        
        return entries.order_by('-created_at')
    
    @classmethod
    def cleanup_expired_entries(cls):
        """Clean up expired blacklist entries."""
        expired_count = cls.objects.filter(
            expires_at__lt=timezone.now(),
            is_permanent=False
        ).delete()[0]
        
        logger.info(f"Cleaned up {expired_count} expired blacklist entries")
        
        return expired_count
    
    @classmethod
    def get_blacklist_statistics(cls, tenant_id: int = None) -> dict:
        """Get blacklist statistics."""
        entries = cls.objects.all()
        
        if tenant_id:
            entries = entries.filter(
                models.Q(tenant_id=tenant_id) | models.Q(applies_to_all_tenants=True)
            )
        
        stats = {
            'total_entries': entries.count(),
            'active_entries': entries.filter(is_active=True).count(),
            'expired_entries': entries.filter(
                expires_at__lt=timezone.now(),
                is_permanent=False
            ).count(),
            'permanent_entries': entries.filter(is_permanent=True).count(),
            'entries_by_type': {},
            'entries_by_severity': {},
            'entries_by_action': {},
            'total_hits': entries.aggregate(
                total_hits=models.Sum('hit_count')
            )['total_hits'] or 0,
            'most_hit_entries': entries.order_by('-hit_count')[:10],
        }
        
        # Group by type
        for blacklist_type, _ in cls._meta.get_field('blacklist_type').choices:
            count = entries.filter(blacklist_type=blacklist_type).count()
            if count > 0:
                stats['entries_by_type'][blacklist_type] = count
        
        # Group by severity
        for severity, _ in cls._meta.get_field('severity').choices:
            count = entries.filter(severity=severity).count()
            if count > 0:
                stats['entries_by_severity'][severity] = count
        
        # Group by action
        for action, _ in cls._meta.get_field('action').choices:
            count = entries.filter(action=action).count()
            if count > 0:
                stats['entries_by_action'][action] = count
        
        return stats


class BlacklistHit(models.Model):
    """
    Model for tracking blacklist hits.
    
    Stores detailed information about when blacklist entries are matched.
    """
    
    blacklist_entry = models.ForeignKey(
        RoutingBlacklist,
        on_delete=models.CASCADE,
        related_name='hits',
        verbose_name=_('Blacklist Entry'),
        help_text=_('Blacklist entry that was matched')
    )
    
    request_data = models.JSONField(
        _('Request Data'),
        default=dict,
        help_text=_('Request data that triggered the blacklist hit')
    )
    
    hit_time = models.DateTimeField(
        _('Hit Time'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When the blacklist entry was matched')
    )
    
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        null=True,
        blank=True,
        help_text=_('IP address that triggered the hit')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        null=True,
        blank=True,
        help_text=_('User agent string from the request')
    )
    
    referer = models.URLField(
        _('Referer'),
        null=True,
        blank=True,
        help_text=_('Referer URL from the request')
    )
    
    class Meta:
        db_table = 'offer_routing_blacklist_hit'
        verbose_name = _('Blacklist Hit')
        verbose_name_plural = _('Blacklist Hits')
        ordering = ['-hit_time']
        indexes = [
            models.Index(fields=['blacklist_entry', 'hit_time'], name='idx_blacklist_entry_hit_ti_c91'),
            models.Index(fields=['hit_time'], name='idx_hit_time_1307'),
            models.Index(fields=['ip_address'], name='idx_ip_address_1308'),
        ]
    
    def __str__(self):
        return f"Hit: {self.blacklist_entry.target_value} at {self.hit_time}"


# Signal handlers for blacklist management
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=RoutingBlacklist)
def blacklist_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for blacklist entries."""
    if created:
        logger.info(f"New blacklist entry created: {instance.blacklist_type} - {instance.target_value}")
        
        # Clear cache for blacklist checks
        from django.core.cache import cache
        cache.delete_pattern('blacklist_*')
        
        # Trigger blacklist analysis tasks
        from ..tasks.blacklist import analyze_blacklist_entry
        analyze_blacklist_entry.delay(instance.id)

@receiver(post_delete, sender=RoutingBlacklist)
def blacklist_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for blacklist entries."""
    logger.info(f"Blacklist entry deleted: {instance.blacklist_type} - {instance.target_value}")
    
    # Clear cache for blacklist checks
    from django.core.cache import cache
    cache.delete_pattern('blacklist_*')
