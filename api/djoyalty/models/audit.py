# api/djoyalty/models/audit.py
"""
Audit Log + CustomerDevice Models।
AdminAuditLog: every admin action recorded।
CustomerDevice: FCM tokens for push notifications।
ProductCatalogRule: SKU-level earn rules।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class AdminAuditLog(models.Model):
    """
    Admin/system activity audit log।
    Every important action (points adjust, tier change, fraud action) recorded।
    World: Voucherify full audit trail, Open Loyalty event log।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_logs',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_logs',
        verbose_name='Affected Customer',
    )

    action = models.CharField(max_length=100, verbose_name='Action')
    action_category = models.CharField(
        max_length=30,
        choices=[
            ('points', 'Points Adjustment'),
            ('tier', 'Tier Change'),
            ('redemption', 'Redemption'),
            ('fraud', 'Fraud Action'),
            ('customer', 'Customer Management'),
            ('campaign', 'Campaign'),
            ('offer', 'Offer/OfferWall'),
            ('cashout', 'Cashout'),
            ('system', 'System'),
            ('api', 'API Call'),
            ('auth', 'Authentication'),
            ('other', 'Other'),
        ],
        default='other',
    )

    # Who performed the action
    performed_by = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name='Performed By (admin email or system)',
    )
    performed_by_ip = models.GenericIPAddressField(null=True, blank=True)

    # What changed
    old_value = models.JSONField(null=True, blank=True, verbose_name='Old Value')
    new_value = models.JSONField(null=True, blank=True, verbose_name='New Value')
    description = models.TextField(null=True, blank=True)

    # Reference
    object_type = models.CharField(max_length=100, null=True, blank=True, verbose_name='Object Type')
    object_id = models.CharField(max_length=50, null=True, blank=True, verbose_name='Object ID')

    # Request metadata
    request_id = models.CharField(max_length=100, null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)

    severity = models.CharField(
        max_length=10,
        choices=[('info', 'Info'), ('warning', 'Warning'), ('critical', 'Critical')],
        default='info',
    )
    is_sensitive = models.BooleanField(default=False, verbose_name='Sensitive Action')

    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Admin Audit Log'
        verbose_name_plural = 'Admin Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['action_category', 'timestamp']),
            models.Index(fields=['customer', 'timestamp']),
            models.Index(fields=['performed_by']),
            models.Index(fields=['severity', 'timestamp']),
        ]

    def __str__(self):
        return (
            f'AuditLog({self.action_category}/{self.action}: '
            f'{self.performed_by} -> {self.customer.code if self.customer else "system"})'
        )

    @classmethod
    def log(cls, action: str, category: str = 'other', customer=None,
            performed_by: str = 'system', old_value=None, new_value=None,
            description: str = '', severity: str = 'info',
            object_type: str = None, object_id: str = None,
            tenant=None, request=None):
        """Quick log helper।"""
        try:
            obj = cls.objects.create(
                tenant=tenant or (customer.tenant if customer else None),
                customer=customer,
                action=action,
                action_category=category,
                performed_by=performed_by,
                old_value=old_value,
                new_value=new_value,
                description=description,
                severity=severity,
                object_type=object_type,
                object_id=str(object_id) if object_id else None,
                performed_by_ip=request.META.get('REMOTE_ADDR') if request else None,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if request else None,
            )
            return obj
        except Exception as e:
            logger.error('AdminAuditLog.log error: %s', e)
            return None


class CustomerDevice(models.Model):
    """
    Customer device FCM token storage।
    Required for Firebase push notifications।
    World: fcm-django library pattern।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='devices',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_devices',
    )
    fcm_token = models.CharField(
        max_length=500, unique=True,
        verbose_name='FCM Registration Token',
    )
    device_type = models.CharField(
        max_length=10,
        choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')],
        default='android',
    )
    device_name = models.CharField(max_length=200, null=True, blank=True)
    device_model = models.CharField(max_length=200, null=True, blank=True)
    app_version = models.CharField(max_length=20, null=True, blank=True)
    os_version = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)
    registered_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Device'
        verbose_name_plural = 'Customer Devices'
        ordering = ['-last_used']
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['fcm_token']),
        ]

    def __str__(self):
        return f'Device({self.customer.code}: {self.device_type} [{self.device_name or "unknown"}])'


class ProductCatalogRule(models.Model):
    """
    Product/SKU-level earn rules।
    Specific products = more/less points।
    World: Voucherify product-level rules, Open Loyalty SKU targeting।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='product_catalog_rules',
    )
    name = models.CharField(max_length=200, verbose_name='Rule Name')
    description = models.TextField(null=True, blank=True)

    # Product targeting
    rule_type = models.CharField(
        max_length=20,
        choices=[
            ('sku', 'Specific SKU/Product ID'),
            ('category', 'Product Category'),
            ('brand', 'Brand'),
            ('price_range', 'Price Range'),
        ],
        default='category',
    )
    target_value = models.CharField(
        max_length=200,
        verbose_name='Target Value',
        help_text='SKU, category name, brand name, or price range (min-max)',
    )

    # Points
    earn_type = models.CharField(
        max_length=20,
        choices=[
            ('multiplier', 'Multiplier (× base rate)'),
            ('fixed', 'Fixed Points'),
            ('percentage', '% of Price'),
            ('bonus', 'Bonus Points on Top'),
            ('exclude', 'Exclude (no points)'),
        ],
        default='multiplier',
    )
    value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1'),
        verbose_name='Value (multiplier, fixed pts, or %)',
    )

    # Tier-specific override
    tier_overrides = models.JSONField(
        default=dict, blank=True,
        verbose_name='Tier Overrides',
        help_text='{"gold": 2.0, "platinum": 3.0} -- tier-specific multipliers',
    )

    priority = models.IntegerField(default=0, verbose_name='Priority (higher = first)')
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Product Catalog Rule'
        verbose_name_plural = 'Product Catalog Rules'
        ordering = ['-priority', '-created_at']
        # AUDIT FIX (4): Added indexes -- (tenant, rule_type) covers the primary
        # query pattern: load active rules by type for a tenant.
        # (is_active, valid_from, valid_until) covers time-window filtering.
        indexes = [
            models.Index(fields=['tenant', 'rule_type'],
                         name='pcrule_tenant_type_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='pcrule_tenant_active_idx'),
            models.Index(fields=['is_active', 'valid_from', 'valid_until'],
                         name='pcrule_active_dates_idx'),
        ]

    def __str__(self):
        return f'ProductRule({self.name}: {self.rule_type}={self.target_value} -> {self.earn_type} {self.value})'


class MultiCurrencyRate(models.Model):
    """
    Multi-currency support -- points value in different currencies।
    World: Global loyalty programs supporting USD, EUR, BDT, GBP, etc।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='currency_rates',
    )
    currency_code = models.CharField(max_length=10, verbose_name='Currency Code (ISO 4217)')
    currency_name = models.CharField(max_length=100)
    currency_symbol = models.CharField(max_length=10)

    # Exchange rates
    earn_rate = models.DecimalField(
        max_digits=14, decimal_places=6, default=Decimal('1'),
        verbose_name='Points per 1 unit of this currency',
    )
    redeem_rate = models.DecimalField(
        max_digits=14, decimal_places=6, default=Decimal('0.01'),
        verbose_name='Currency value per 1 point',
    )
    base_to_currency_rate = models.DecimalField(
        max_digits=14, decimal_places=6, default=Decimal('1'),
        verbose_name='Base currency (BDT) to this currency rate',
    )

    is_active = models.BooleanField(default=True)
    is_base = models.BooleanField(default=False, verbose_name='Is Base Currency')
    effective_date = models.DateField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Multi-Currency Rate'
        verbose_name_plural = 'Multi-Currency Rates'
        unique_together = [('tenant', 'currency_code')]
        ordering = ['currency_code']
        # AUDIT FIX (4): Added indexes -- (tenant, currency_code) already covered
        # by unique_together but compound index explicit here for read performance.
        # (tenant, is_active) covers 'list all active currencies for tenant'.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='mcrate_tenant_active_idx'),
            models.Index(fields=['is_active', 'effective_date'],
                         name='mcrate_active_date_idx'),
        ]

    def __str__(self):
        return f'Currency({self.currency_code}: 1 unit = {self.earn_rate} pts)'


class SystemConfig(models.Model):
    """
    Per-tenant system configuration -- key/value store।
    Replaces hardcoded settings with DB-configurable values।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='system_configs',
    )
    key = models.CharField(max_length=100, verbose_name='Config Key')
    value = models.TextField(verbose_name='Config Value')
    description = models.CharField(max_length=300, null=True, blank=True)
    value_type = models.CharField(
        max_length=10,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('decimal', 'Decimal'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string',
    )
    is_sensitive = models.BooleanField(default=False, verbose_name='Sensitive (hide in UI)')
    updated_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'System Config'
        unique_together = [('tenant', 'key')]
        ordering = ['key']
        # AUDIT FIX (4): Added indexes -- (tenant, key) already covered by
        # unique_together; extra index on (tenant, is_sensitive) for admin
        # views that filter sensitive configs.
        indexes = [
            models.Index(fields=['tenant', 'is_sensitive'],
                         name='syscfg_tenant_sensitive_idx'),
        ]

    def __str__(self):
        return f'Config({self.key}: {"***" if self.is_sensitive else self.value[:50]})'

    def get_typed_value(self):
        """Return value as correct Python type।"""
        import json
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'decimal':
            return Decimal(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'json':
            return json.loads(self.value)
        return self.value
