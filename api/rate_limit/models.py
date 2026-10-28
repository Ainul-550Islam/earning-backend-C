# api/rate_limit/models.py
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Count, Q, F
import json
import hashlib
from datetime import timedelta
from django.db import models as django_models


class TimeStampedModel(models.Model):
    """Abstract base model with created_at and updated_at fields."""
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class HashChainedModel(TimeStampedModel):
    """Abstract base model with SHA-256 hash chaining for integrity."""
    integrity_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    previous_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Override save to update integrity hash."""
        self.update_integrity_hash()
        super().save(*args, **kwargs)
    
    def update_integrity_hash(self):
        """Update SHA-256 integrity hash based on model fields."""
        hash_data = self._get_hash_data()
        hash_string = json.dumps(hash_data, sort_keys=True, default=str)
        self.integrity_hash = hashlib.sha256(hash_string.encode()).hexdigest()
    
    def _get_hash_data(self):
        """Get data for hash calculation."""
        data = {}
        for field in self._meta.fields:
            if field.name not in ['id', 'integrity_hash', 'previous_hash', 'created_at', 'updated_at']:
                value = getattr(self, field.name)
                if value is not None:
                    data[field.name] = value
        return data
    
    def verify_integrity(self):
        """Verify model integrity."""
        current_hash = self.integrity_hash
        self.update_integrity_hash()
        return current_hash == self.integrity_hash


class RateLimitConfig(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    RATE_LIMIT_TYPES = [
        ('user', 'User-based'),
        ('ip', 'IP-based'),
        ('endpoint', 'Endpoint-based'),
        ('global', 'Global'),
        ('referral', 'Referral-based'),
        ('task', 'Task-based'),
        ('offer_wall', 'Offer Wall-based'),
    ]
    
    TIME_UNITS = [
        ('second', 'Second'),
        ('minute', 'Minute'),
        ('hour', 'Hour'),
        ('day', 'Day'),
    ]
    
    # Basic fields
    name = models.CharField(max_length=100, null=True, blank=True)
    rate_limit_type = models.CharField(max_length=20, choices=RATE_LIMIT_TYPES, null=True, blank=True)
    requests_per_unit = models.IntegerField(default=100)
    requests_per_minute = models.IntegerField(null=True, blank=True)
    burst_size = models.IntegerField(null=True, blank=True)
    burst_multiplier = models.FloatField(default=1.0)
    time_unit = models.CharField(max_length=10, choices=TIME_UNITS, default='hour', null=True, blank=True)
    time_value = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    # Target fields
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    endpoint = models.CharField(max_length=500, null=True, blank=True)
    task_type = models.CharField(max_length=50, null=True, blank=True)
    offer_wall = models.CharField(max_length=100, null=True, blank=True)
    
    # Whitelist/Blacklist
    whitelist = models.JSONField(default=list, blank=True)
    blacklist = models.JSONField(default=list, blank=True)
    bypass_keys = models.JSONField(default=list, blank=True)
    
    # Statistics
    hit_count = models.IntegerField(default=0)
    block_count = models.IntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    
    response_status = models.IntegerField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    method = models.CharField(max_length=10, blank=True, default="")
    is_allowed = models.BooleanField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rate_limit_type', 'is_active'], name='idx_rate_limit_type_is_act_c12'),
            models.Index(fields=['endpoint'], name='idx_endpoint_1661'),
            models.Index(fields=['ip_address'], name='idx_ip_address_1662'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['name'], 
                condition=models.Q(name__isnull=False),
                name='unique_rate_limit_config_name'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.requests_per_unit} per {self.time_unit}"

    @property
    def ratelimitlog_set(self):
        """Alias for logs reverse manager - backwards compat."""
        return self.logs
    
    def get_api_health(self):
        if self.hit_count == 0:
            return 100
        
        block_rate = (self.block_count / self.hit_count) * 100
        
        if block_rate >= 90:
            return 10
        elif block_rate >= 70:
            return 30
        elif block_rate >= 50:
            return 50
        elif block_rate >= 30:
            return 70
        else:
            return 90
    
    def simulate_impact(self, hours=1):
        from_date = timezone.now() - timedelta(hours=hours)
        
        logs = RateLimitLog.objects.filter(
            timestamp__gte=from_date
        )
        
        if self.rate_limit_type == 'endpoint' and self.endpoint:
            logs = logs.filter(endpoint=self.endpoint)
        elif self.rate_limit_type == 'ip' and self.ip_address:
            logs = logs.filter(ip_address=self.ip_address)
        elif self.rate_limit_type == 'user' and self.user:
            logs = logs.filter(user=self.user)
        else:
            return {'error': 'Cannot simulate for this config type'}
        
        total_requests = logs.count()
        would_block = max(0, total_requests - self.requests_per_unit)
        
        return {
            'total_requests': total_requests,
            'would_block': would_block,
            'block_percentage': (would_block / max(total_requests, 1)) * 100,
            'simulation_period': f'{hours} hour(s)'
        }


class RateLimitLog(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    STATUS_CHOICES = [
        ('allowed', 'Allowed'),
        ('blocked', 'Blocked'),
        ('exceeded', 'Exceeded'),
    ]
    
    # Request info
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    endpoint = models.CharField(max_length=500, null=True, blank=True)
    request_method = models.CharField(max_length=10, default='GET', null=True, blank=True)
    user_agent = models.TextField(blank=True)
    country = models.CharField(max_length=10, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    method = models.CharField(max_length=10, blank=True, null=True)

    # Rate limit info
    config = models.ForeignKey(RateLimitConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, null=True, blank=True)
    requests_count = models.IntegerField(default=1)
    
    # Earning app specific
    task_id = models.CharField(max_length=100, null=True, blank=True)
    offer_id = models.CharField(max_length=100, null=True, blank=True)
    referral_code = models.CharField(max_length=50, null=True, blank=True)
    
    # Suspicion scoring
    suspicion_score = models.IntegerField(default=0)
    
    response_status = models.IntegerField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    method = models.CharField(max_length=10, blank=True, default="")
    is_allowed = models.BooleanField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    response_time = models.FloatField(null=True, blank=True)  # seconds

    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp'], name='idx_timestamp_1663'),
            models.Index(fields=['user', 'status'], name='idx_user_status_1664'),
            models.Index(fields=['ip_address', 'timestamp'], name='idx_ip_address_timestamp_1665'),
            models.Index(fields=['endpoint', 'timestamp'], name='idx_endpoint_timestamp_1666'),
        ]
    
    def __str__(self):
        return f"{self.ip_address} - {self.endpoint} - {self.status}"
    
    def calculate_suspicion_score(self):
        score = 0
        
        if self.requests_count > 100:
            score += 30
        elif self.requests_count > 50:
            score += 20
        elif self.requests_count > 20:
            score += 10
        
        if self.status == 'blocked':
            score += 20
        
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_blocks = RateLimitLog.objects.filter(
            ip_address=self.ip_address,
            status='blocked',
            timestamp__gte=one_hour_ago
        ).count()
        score += min(recent_blocks * 5, 30)
        
        ip_users = RateLimitLog.objects.filter(
            ip_address=self.ip_address,
            timestamp__gte=one_hour_ago
        ).values('user').distinct().count()
        if ip_users > 3:
            score += 20
        
        self.suspicion_score = min(score, 100)
        return self.suspicion_score
    
    def save(self, *args, **kwargs):
        if not self.suspicion_score:
            self.calculate_suspicion_score()
        
        if self.config:
            # Atomic update using F() expressions to avoid N+1 writes and race conditions
            update_fields = {
                'hit_count': F('hit_count') + 1,
                'last_hit_at': self.timestamp
            }
            if self.status == 'blocked':
                update_fields['block_count'] = F('block_count') + 1
            
            RateLimitConfig.objects.filter(pk=self.config.pk).update(**update_fields)
        
        super().save(*args, **kwargs)



class UserRateLimitProfileManager(models.Manager):
    def create(self, **kwargs):
        """Use get_or_create to avoid UNIQUE constraint violations."""
        user = kwargs.get('user')
        if user:
            obj, created = self.get_or_create(user=user, defaults=kwargs)
            if not created:
                for k, v in kwargs.items():
                    if k != 'user':
                        try:
                            setattr(obj, k, v)
                        except Exception:
                            pass
                try:
                    valid_fields = {f.name for f in obj._meta.get_fields()}
                    update_fields = [k for k in kwargs if k != 'user' and k in valid_fields]
                    if update_fields:
                        obj.save(update_fields=update_fields)
                except Exception:
                    try:
                        obj.save()
                    except Exception:
                        pass
            return obj
        return super().create(**kwargs)


class UserRateLimitProfile(models.Model):
    objects = UserRateLimitProfileManager()

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        db_index=True,
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratelimitprofile', null=True, blank=True)
    
    # Premium status
    is_premium = models.BooleanField(default=False)
    premium_until = models.DateTimeField(null=True, blank=True)
    
    # Custom limits
    custom_daily_limit = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    custom_hourly_limit = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    
    # Current usage
    current_usage = models.IntegerField(default=0)
    daily_usage = models.IntegerField(default=0)
    hourly_usage = models.IntegerField(default=0)
    
    # Statistics
    total_requests = models.IntegerField(default=0)
    blocked_requests = models.IntegerField(default=0)
    last_request_at = models.DateTimeField(null=True, blank=True)
    
    # Health metrics
    api_health_score = models.IntegerField(default=100)
    endpoint_health = models.JSONField(default=dict, blank=True)
    
    # Suspicion
    suspicion_score = models.IntegerField(default=0)
    
    response_status = models.IntegerField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    method = models.CharField(max_length=10, blank=True, default="")
    is_allowed = models.BooleanField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user} - Health: {self.api_health_score}, Suspicion: {self.suspicion_score}"
    
    def get_usage_percentage(self):
        daily_limit = self.custom_daily_limit or 1000
        if daily_limit > 0:
            return (self.current_usage / daily_limit) * 100
        return 0
    
    def update_health_score(self):
        if self.total_requests == 0:
            self.api_health_score = 100
            return
        
        block_rate = (self.blocked_requests / self.total_requests) * 100
        
        if block_rate >= 30:
            self.api_health_score = 30
        elif block_rate >= 20:
            self.api_health_score = 50
        elif block_rate >= 10:
            self.api_health_score = 70
        elif block_rate >= 5:
            self.api_health_score = 80
        else:
            self.api_health_score = 95
        
        one_day_ago = timezone.now() - timedelta(days=1)
        endpoints = RateLimitLog.objects.filter(
            user=self.user,
            timestamp__gte=one_day_ago
        ).values('endpoint').annotate(
            total=Count('id'),
            blocked=Count('id', filter=Q(status='blocked'))
        )
        
        endpoint_health = {}
        for endpoint in endpoints:
            if endpoint['total'] > 0:
                health = 100 - (endpoint['blocked'] / endpoint['total'] * 100)
                endpoint_health[endpoint['endpoint']] = max(0, min(100, health))
        
        self.endpoint_health = endpoint_health
        self.save()
    
    def check_suspicion(self):
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        recent_logs = RateLimitLog.objects.filter(
            user=self.user,
            timestamp__gte=one_hour_ago
        )
        
        if recent_logs.count() > 100:
            self.suspicion_score = min(100, self.suspicion_score + 30)
        elif recent_logs.filter(status='blocked').count() > 10:
            self.suspicion_score = min(100, self.suspicion_score + 20)
        
        ip_count = recent_logs.values('ip_address').distinct().count()
        if ip_count > 3:
            self.suspicion_score = min(100, self.suspicion_score + 25)
        
        self.save()
        return self.suspicion_score


class IPBlockList(HashChainedModel):
    """Cryptographically secure IP blocking system."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    
    BLOCK_TYPES = [
        ('single', 'Single IP'),
        ('range', 'IP Range'),
        ('subnet', 'Subnet'),
        ('permanent', 'Permanent Block'),
        ('temporary', 'Temporary Block'),
    ]
    
    BLOCK_REASONS = [
        ('abuse', 'Abuse'),
        ('fraud', 'Fraud'),
        ('spam', 'Spam'),
        ('malicious', 'Malicious Activity'),
        ('malicious_activity', 'Malicious Activity'),
        ('manual', 'Manual Block'),
        ('automatic', 'Automatic Detection'),
        ('suspicious_activity', 'Suspicious Activity'),
    ]
    
    # IP information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ip_range_start = models.GenericIPAddressField(null=True, blank=True)
    ip_range_end = models.GenericIPAddressField(null=True, blank=True)
    subnet = models.CharField(max_length=18, null=True, blank=True)  # CIDR notation
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, default='single')
    
    # Block details
    reason = models.CharField(max_length=30, choices=BLOCK_REASONS, default='automatic')
    block_reason = models.CharField(max_length=200, blank=True, default='')  # human-readable reason
    blocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='ip_blocks_created')
    
    # Status and timing
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    permanent = models.BooleanField(default=False)
    
    # Statistics
    block_count = models.IntegerField(default=0)
    last_blocked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'is_active'], name='idx_ip_active_1001'),
            models.Index(fields=['block_type', 'is_active'], name='idx_type_active_1002'),
            models.Index(fields=['expires_at'], name='idx_expires_1003'),
        ]
    
    def __str__(self):
        if self.block_type == 'single':
            return f"{self.ip_address} - {self.block_reason}"
        elif self.block_type == 'range':
            return f"Blocked Range: {self.ip_range_start} - {self.ip_range_end}"
        else:
            return f"Blocked Subnet: {self.subnet}"
    
    def is_expired(self):
        """Check if block has expired."""
        if self.permanent or not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def is_ip_blocked(self, ip_address):
        """Check if given IP is blocked by this rule."""
        if not self.is_active or self.is_expired():
            return False
        
        if self.block_type == 'single':
            return self.ip_address == ip_address
        elif self.block_type == 'range':
            if self.ip_range_start and self.ip_range_end:
                return self.ip_range_start <= ip_address <= self.ip_range_end
        elif self.block_type == 'subnet':
            if self.subnet:
                import ipaddress
                try:
                    network = ipaddress.ip_network(self.subnet, strict=False)
                    return ipaddress.ip_address(ip_address) in network
                except:
                    pass
        
        return False


class AbuseReport(HashChainedModel):
    """Abuse reporting and tracking system."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    
    ABUSE_TYPES = [
        ('rate_limit', 'Rate Limit Abuse'),
        ('spam', 'Spam Activity'),
        ('fraud', 'Fraudulent Activity'),
        ('malicious', 'Malicious Behavior'),
        ('bot', 'Bot Activity'),
        ('other', 'Other'),
    ]
    
    # Target information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Abuse details
    abuse_type = models.CharField(max_length=20, choices=ABUSE_TYPES, default='rate_limit')
    endpoint = models.CharField(max_length=500, null=True, blank=True, default='')
    pattern = models.CharField(max_length=100, blank=True)  # Abuse pattern detected
    
    # Statistics
    count_24h = models.IntegerField(default=0)
    count_7d = models.IntegerField(default=0)
    count_total = models.IntegerField(default=0)
    
    # Timing
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    
    # Description and evidence
    description = models.TextField(blank=True, default='')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="abuse_reporter")
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="abuse_reported")
    evidence = models.JSONField(default=dict, blank=True)

    # Status
    reported_ip = models.GenericIPAddressField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    is_blocked = models.BooleanField(default=False)
    is_investigated = models.BooleanField(default=False)
    severity = models.IntegerField(default=1, choices=[(i, f'Level {i}') for i in range(1, 6)])
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['ip_address', 'abuse_type'], name='idx_ip_abuse_1004'),
            models.Index(fields=['user', 'abuse_type'], name='idx_user_abuse_1005'),
            models.Index(fields=['is_blocked', 'last_seen'], name='idx_blocked_last_1006'),
            models.Index(fields=['severity'], name='idx_severity_1007'),
        ]
    
    def __str__(self):
        return f"{self.abuse_type} - {self.ip_address} - Severity: {self.severity}"
    
    def update_counts(self):
        """Update abuse counts."""
        from django.utils import timezone
        now = timezone.now()
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        
        # Count reports in different time periods
        self.count_24h = AbuseReport.objects.filter(
            ip_address=self.ip_address,
            abuse_type=self.abuse_type,
            created_at__gte=one_day_ago
        ).count()
        
        self.count_7d = AbuseReport.objects.filter(
            ip_address=self.ip_address,
            abuse_type=self.abuse_type,
            created_at__gte=seven_days_ago
        ).count()
        
        self.count_total = AbuseReport.objects.filter(
            ip_address=self.ip_address,
            abuse_type=self.abuse_type
        ).count()
        
        self.last_seen = now
        self.save()
    
    def should_block(self):
        """Determine if this abuse should trigger blocking."""
        # Auto-block based on severity and frequency
        if self.severity >= 4:
            return True
        
        if self.count_24h >= 10:
            return True
        
        if self.count_7d >= 50:
            return True
        
        return False


class RateLimitException(HashChainedModel):
    """Rate limit exception tracking system."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    
    EXCEPTION_TYPES = [
        ('whitelist', 'Whitelisted'),
        ('premium', 'Premium User'),
        ('emergency', 'Emergency Access'),
        ('maintenance', 'Maintenance Override'),
        ('custom', 'Custom Exception'),
    ]
    
    # Target information
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    endpoint_pattern = models.CharField(max_length=500, blank=True)
    
    # Exception details
    exception_type = models.CharField(max_length=20, choices=EXCEPTION_TYPES, default='custom')
    reason = models.TextField(blank=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_exceptions')
    
    # Exception parameters
    multiplier = models.FloatField(default=1.0)  # Rate limit multiplier
    max_requests = models.IntegerField(null=True, blank=True)  # Override max requests
    
    # Status and timing
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    permanent = models.BooleanField(default=False)
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active'], name='idx_user_active_1008'),
            models.Index(fields=['ip_address', 'is_active'], name='idx_ip_active_1009'),
            models.Index(fields=['exception_type', 'is_active'], name='idx_type_active_1010'),
        ]
    
    def __str__(self):
        target = self.user.username if self.user else self.ip_address
        return f"{self.exception_type} - {self.user}"
    
    def is_expired(self):
        """Check if exception has expired."""
        if self.permanent or not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def applies_to_request(self, user, ip_address, endpoint):
        """Check if exception applies to given request."""
        if not self.is_active or self.is_expired():
            return False
        
        # Check user match
        if self.user and user and self.user == user:
            return True
        
        # Check IP match
        if self.ip_address and self.ip_address == ip_address:
            return True
        
        # Check endpoint pattern
        if self.endpoint_pattern and endpoint:
            import re
            return bool(re.match(self.endpoint_pattern, endpoint))
        
        return False


class RateLimitInsight(HashChainedModel):
    """Rate limit analytics and insights."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    
    # Date information
    date = models.DateField()
    hour = models.IntegerField(null=True, blank=True)  # For hourly insights
    
    # Request statistics
    total_requests = models.IntegerField(default=0)
    allowed_requests = models.IntegerField(default=0)
    blocked_requests = models.IntegerField(default=0)
    
    # Top abusers and endpoints (JSON data)
    top_abusers = models.JSONField(default=list, blank=True)
    top_endpoints = models.JSONField(default=list, blank=True)
    top_ips = models.JSONField(default=list, blank=True)
    
    # Abuse statistics
    abuse_reports_count = models.IntegerField(default=0)
    auto_blocks_count = models.IntegerField(default=0)
    manual_blocks_count = models.IntegerField(default=0)
    
    # Performance metrics
    avg_response_time = models.FloatField(null=True, blank=True)
    peak_requests_per_minute = models.IntegerField(default=0)
    
    peak_hour = models.IntegerField(null=True, blank=True)  # 0-23
    # Additional metrics
    unique_users = models.IntegerField(default=0)
    unique_ips = models.IntegerField(default=0)
    error_rate = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-date', '-hour']
        indexes = [
            models.Index(fields=['date', 'hour'], name='idx_date_hour_1011'),
            models.Index(fields=['date'], name='idx_date_1012'),
            models.Index(fields=['total_requests'], name='idx_total_req_1013'),
        ]
        unique_together = [['date', 'hour']]
    
    def __str__(self):
        return f"{self.date} - {self.total_requests} requests"
    
    def calculate_block_rate(self):
        """Calculate block rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.blocked_requests / self.total_requests) * 100
    
    def calculate_error_rate(self):
        """Calculate error rate percentage."""
        return self.error_rate
    
    def get_health_score(self):
        """Get overall health score (0-100)."""
        block_rate = self.calculate_block_rate()
        error_rate = self.calculate_error_rate()
        
        # Base score starts at 100
        score = 100
        
        # Deduct for high block rate
        if block_rate > 20:
            score -= 30
        elif block_rate > 10:
            score -= 15
        elif block_rate > 5:
            score -= 5
        
        # Deduct for high error rate
        if error_rate > 10:
            score -= 20
        elif error_rate > 5:
            score -= 10
        elif error_rate > 2:
            score -= 5
        
        return max(0, score)