# api/rate_limit/models.py
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Count, Q
import json
from datetime import timedelta


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
    ]
    
    TIME_UNITS = [
        ('second', 'Second'),
        ('minute', 'Minute'),
        ('hour', 'Hour'),
        ('day', 'Day'),
    ]
    
    # Basic fields
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    rate_limit_type = models.CharField(max_length=20, choices=RATE_LIMIT_TYPES, null=True, blank=True)
    requests_per_unit = models.IntegerField(default=100)
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rate_limit_type', 'is_active'], name='idx_rate_limit_type_is_act_c12'),
            models.Index(fields=['endpoint'], name='idx_endpoint_1661'),
            models.Index(fields=['ip_address'], name='idx_ip_address_1662'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_rate_limit_type_display()})"
    
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
    ip_address = models.GenericIPAddressField()
    endpoint = models.CharField(max_length=500, null=True, blank=True)
    request_method = models.CharField(max_length=10, default='GET', null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Rate limit info
    config = models.ForeignKey(RateLimitConfig, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, null=True, blank=True)
    requests_count = models.IntegerField(default=1)
    
    # Earning app specific
    task_id = models.CharField(max_length=100, null=True, blank=True)
    offer_id = models.CharField(max_length=100, null=True, blank=True)
    referral_code = models.CharField(max_length=50, null=True, blank=True)
    
    # Suspicion scoring
    suspicion_score = models.IntegerField(default=0)
    
    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp'], name='idx_timestamp_1663'),
            models.Index(fields=['user', 'status'], name='idx_user_status_1664'),
            models.Index(fields=['ip_address', 'timestamp'], name='idx_ip_address_timestamp_1665'),
            models.Index(fields=['endpoint', 'timestamp'], name='idx_endpoint_timestamp_1666'),
        ]
    
    def __str__(self):
        return f"{self.timestamp}: {self.ip_address} - {self.endpoint} ({self.status})"
    
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
            self.config.hit_count += 1
            if self.status == 'blocked':
                self.config.block_count += 1
            self.config.last_hit_at = self.timestamp
            self.config.save()
        
        super().save(*args, **kwargs)


class UserRateLimitProfile(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rate_limit_userratelimitprofile_user', null=True, blank=True)
    
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - Rate Limit Profile"
    
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