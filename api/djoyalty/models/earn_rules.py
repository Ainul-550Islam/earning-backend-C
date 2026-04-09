# api/djoyalty/models/earn_rules.py
from django.db import models
from ..choices import EARN_RULE_TYPE_CHOICES, EARN_RULE_TRIGGER_CHOICES
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import ActiveEarnRuleManager


class EarnRule(models.Model):
    """Points earn rule definition।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_earnrule_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    rule_type = models.CharField(max_length=32, choices=EARN_RULE_TYPE_CHOICES, db_index=True)
    trigger = models.CharField(max_length=32, choices=EARN_RULE_TRIGGER_CHOICES, db_index=True)
    points_value = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    min_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_earn_per_txn = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, null=True, blank=True)
    max_earn_per_day = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, null=True, blank=True)
    applicable_tiers = models.JSONField(null=True, blank=True, help_text='List of tier names, null=all tiers')
    is_active = models.BooleanField(default=True, db_index=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveEarnRuleManager()

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-priority', 'name']
        indexes = [models.Index(fields=['is_active', 'trigger'])]

    def __str__(self):
        return f'{self.name} [{self.rule_type}/{self.trigger}]'


class EarnRuleCondition(models.Model):
    """Additional conditions for earn rules।"""

    earn_rule = models.ForeignKey(
        'EarnRule', on_delete=models.CASCADE,
        related_name='conditions',
    )
    field = models.CharField(max_length=64)
    operator = models.CharField(
        max_length=16,
        choices=[
            ('eq', '='), ('ne', '!='), ('gt', '>'), ('gte', '>='),
            ('lt', '<'), ('lte', '<='), ('in', 'IN'), ('not_in', 'NOT IN'),
        ],
    )
    value = models.CharField(max_length=256)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.earn_rule.name}: {self.field} {self.operator} {self.value}'


class EarnRuleTierMultiplier(models.Model):
    """Tier-specific multiplier override for earn rule।"""

    earn_rule = models.ForeignKey(
        'EarnRule', on_delete=models.CASCADE,
        related_name='tier_multipliers',
    )
    tier = models.ForeignKey(
        'LoyaltyTier', on_delete=models.CASCADE,
        related_name='earn_multipliers',
    )
    multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('earn_rule', 'tier')]

    def __str__(self):
        return f'{self.earn_rule.name} × {self.multiplier} for {self.tier.name}'


class EarnTransaction(models.Model):
    """Points earn এর record।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_earntransaction_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='earn_transactions',
    )
    earn_rule = models.ForeignKey(
        'EarnRule', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='earn_transactions',
    )
    txn = models.ForeignKey(
        'Txn', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='earn_transactions',
    )
    points_earned = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    multiplier_applied = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    spend_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']

    def __str__(self):
        return f'+{self.points_earned} pts for {self.customer}'


class BonusEvent(models.Model):
    """Manual/automated bonus points event।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_bonusevent_tenant', db_index=True,
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='bonus_events',
    )
    points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES)
    reason = models.CharField(max_length=256)
    triggered_by = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']

    def __str__(self):
        return f'Bonus +{self.points} pts for {self.customer}: {self.reason}'


class EarnRuleLog(models.Model):
    """Earn rule evaluation log — debug এর জন্য।"""

    earn_rule = models.ForeignKey(
        'EarnRule', on_delete=models.CASCADE,
        related_name='logs',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='earn_rule_logs',
    )
    triggered = models.BooleanField(default=False)
    points_result = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-created_at']

    def __str__(self):
        return f'EarnLog: {self.earn_rule.name} → {self.customer} (triggered={self.triggered})'
