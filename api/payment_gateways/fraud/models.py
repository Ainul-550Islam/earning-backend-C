# FILE 82 of 257 — fraud/models.py
from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

ALL_GW = (('bkash','bKash'),('nagad','Nagad'),('sslcommerz','SSLCommerz'),
          ('amarpay','AmarPay'),('upay','Upay'),('shurjopay','ShurjoPay'),
          ('stripe','Stripe'),('paypal','PayPal'))

class FraudAlert(TimeStampedModel):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fraud_alerts')
    gateway    = models.CharField(max_length=20, choices=ALL_GW)
    amount     = models.DecimalField(max_digits=10, decimal_places=2)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    risk_score = models.IntegerField()
    risk_level = models.CharField(max_length=10, choices=(('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')))
    action     = models.CharField(max_length=10, choices=(('allow','Allow'),('flag','Flag'),('verify','Verify'),('block','Block')))
    reasons    = models.JSONField(default=list)
    metadata   = models.JSONField(default=dict, blank=True)
    resolved   = models.BooleanField(default=False)
    resolved_by= models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_fraud_alerts')
    resolved_at= models.DateTimeField(null=True, blank=True)
    notes      = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name='Fraud Alert'; verbose_name_plural='Fraud Alerts'; ordering=['-created_at']
        indexes=[models.Index(fields=['risk_level']),models.Index(fields=['user','risk_level']),models.Index(fields=['ip_address'])]
    def __str__(self): return f'FraudAlert [{self.risk_level}] user={self.user_id} score={self.risk_score}'

class BlockedIP(TimeStampedModel):
    ip_address = models.GenericIPAddressField(unique=True)
    reason     = models.TextField()
    is_active  = models.BooleanField(default=True)
    blocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='blocked_ips')
    expires_at = models.DateTimeField(null=True, blank=True)
    class Meta: verbose_name='Blocked IP'; verbose_name_plural='Blocked IPs'
    def __str__(self): return f'BlockedIP {self.ip_address}'
    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expires_at and self.expires_at < timezone.now()

class RiskRule(TimeStampedModel):
    name           = models.CharField(max_length=100, unique=True)
    description    = models.TextField(blank=True)
    condition_type = models.CharField(max_length=30, choices=(('amount_gt','Amount >'),('amount_lt','Amount <'),('gateway_is','Gateway is'),('user_attr','User attr')))
    condition_value= models.CharField(max_length=200)
    score          = models.IntegerField()
    reason         = models.CharField(max_length=255)
    priority       = models.IntegerField(default=100)
    is_active      = models.BooleanField(default=True)
    class Meta: verbose_name='Risk Rule'; verbose_name_plural='Risk Rules'; ordering=['priority']
    def __str__(self): return f'RiskRule {self.name} (+{self.score})'
