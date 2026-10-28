# api/djoyalty/models/earn_rules.py
"""
Djoyalty Earn Rule Models।
EarnRule, EarnRuleCondition, EarnRuleTierMultiplier,
EarnTransaction, BonusEvent, EarnRuleLog।

AUDIT FIXES (v2 -- Financial Integrity):
  EarnTransaction.customer:
    Changed on_delete=CASCADE → PROTECT।  Earn transaction records are financial
    audit trails and must survive customer deletion।

  EarnTransaction.reference_id (NEW FIELD):
    EarnTransaction previously had no reference_id field।  PointsLedger has one,
    but EarnTransaction (the trigger record) did not।  When PointsEngine rejects
    a duplicate earn via the ledger's reference_id constraint, the EarnTransaction
    record was still created, producing an orphaned EarnTransaction with no
    corresponding PointsLedger credit।  Adding reference_id to EarnTransaction
    allows callers to deduplicate at the trigger level too, and lets
    EarnRuleEngine.process_earn() be truly idempotent end-to-end।
    Migration: 0014_financial_integrity_constraints.py
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveEarnRuleManager, ActiveManager

logger = logging.getLogger(__name__)


class EarnRule(models.Model):
    """
    Configurable earn rule -- কখন, কতটা points earn হবে।
    Fixed / Percentage / Multiplier types support করে।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='earn_rules',
    )
    name = models.CharField(max_length=200, verbose_name='Rule Name')
    description = models.TextField(null=True, blank=True)

    rule_type = models.CharField(
        max_length=20,
        choices=[
            ('fixed', 'Fixed Points'),
            ('percentage', 'Percentage of Spend'),
            ('multiplier', 'Multiplier'),
        ],
        default='percentage',
        verbose_name='Rule Type',
    )
    trigger = models.CharField(
        max_length=30,
        choices=[
            ('purchase', 'Purchase'), ('offer', 'Offer Completion'),
            ('login', 'Login'), ('referral', 'Referral'),
            ('birthday', 'Birthday'), ('signup', 'Signup'),
            ('review', 'Review'), ('social_share', 'Social Share'),
        ],
        default='purchase',
        verbose_name='Trigger',
    )

    points_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1'),
        verbose_name='Points Value',
        help_text='Fixed pts, or % of spend, or multiplier',
    )
    multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
        verbose_name='Multiplier',
    )

    # Constraints
    min_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Minimum Spend',
    )
    max_earn_per_txn = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Max Points per Transaction',
    )
    max_per_day = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Max Points per Day',
    )

    # Tier restriction
    applicable_tiers = models.JSONField(
        default=list, blank=True,
        verbose_name='Applicable Tiers',
        help_text='Empty = all tiers',
    )

    # Validity
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name='Valid From')
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='Valid Until')

    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, verbose_name='Priority (higher = first)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveEarnRuleManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Earn Rule'
        verbose_name_plural = 'Earn Rules'
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['trigger', 'is_active']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f'EarnRule({self.name} [{self.trigger}/{self.rule_type}])'


class EarnRuleCondition(models.Model):
    """
    Additional conditions for an earn rule।
    e.g. min_amount >= 500, tier = gold, day = friday।
    """
    rule = models.ForeignKey(
        EarnRule,
        on_delete=models.CASCADE,
        related_name='conditions',
        verbose_name='Earn Rule',
    )
    condition_type = models.CharField(
        max_length=30,
        choices=[
            ('min_amount', 'Minimum Amount'), ('tier', 'Tier'),
            ('day', 'Day of Week'), ('offer', 'Offer'),
        ],
        verbose_name='Condition Type',
    )
    operator = models.CharField(
        max_length=10,
        choices=[
            ('gt', '>'), ('gte', '>='), ('lt', '<'), ('lte', '<='),
            ('eq', '='), ('in', 'in'),
        ],
        default='gte',
        verbose_name='Operator',
    )
    value = models.CharField(max_length=200, verbose_name='Value')
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Earn Rule Condition'
        # AUDIT FIX (4): (rule,) for loading all conditions for a rule;
        # (condition_type,) for engine routing by condition type.
        indexes = [
            models.Index(fields=['rule'],
                         name='earnrulecond_rule_idx'),
            models.Index(fields=['condition_type'],
                         name='earnrulecond_type_idx'),
        ]

    def __str__(self):
        return f'Condition({self.rule.name}: {self.condition_type} {self.operator} {self.value})'


class EarnRuleTierMultiplier(models.Model):
    """
    Per-tier multiplier override for an earn rule।
    """
    rule = models.ForeignKey(
        EarnRule,
        on_delete=models.CASCADE,
        related_name='tier_multipliers',
        verbose_name='Earn Rule',
    )
    tier = models.ForeignKey(
        'djoyalty.LoyaltyTier',
        on_delete=models.CASCADE,
        related_name='earn_multipliers',
        verbose_name='Tier',
    )
    multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
        verbose_name='Tier Multiplier',
    )

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Earn Rule Tier Multiplier'
        unique_together = [('rule', 'tier')]
        # AUDIT FIX (4): (rule,) for loading all tier multipliers for a rule.
        indexes = [
            models.Index(fields=['rule'],
                         name='earnruletm_rule_idx'),
        ]

    def __str__(self):
        return f'TierMultiplier({self.rule.name} × {self.tier.name}: {self.multiplier})'


class EarnTransaction(models.Model):
    """
    Record of points earned from an earn rule।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  Earn transaction records are
        # financial audit trails and must survive customer deletion।
        on_delete=models.PROTECT,
        related_name='earn_transactions',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='earn_transactions',
    )
    rule = models.ForeignKey(
        EarnRule,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions',
        verbose_name='Earn Rule',
    )

    spend_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Spend Amount',
    )
    points_earned = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Points Earned',
    )
    source = models.CharField(max_length=50, default='purchase', verbose_name='Source')
    source_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='Source ID')

    # AUDIT FIX (v2): Added reference_id।
    # Without this field, if PointsEngine rejects a duplicate earn (via the
    # PointsLedger unique reference_id constraint), the EarnTransaction record
    # is still written, producing an orphaned record with no ledger credit।
    # Callers should pass the same reference_id here as they pass to
    # PointsEngine.earn(), so EarnRuleEngine.process_earn() can deduplicate at
    # the trigger level too।
    # Migration: 0014_financial_integrity_constraints.py
    reference_id = models.CharField(
        max_length=100, null=True, blank=True,
        db_index=True,
        verbose_name='Reference ID',
        help_text='Idempotency reference -- same as PointsLedger.reference_id',
    )

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Earn Transaction'
        verbose_name_plural = 'Earn Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            # reference_id index added via db_index=True on the field itself
        ]

    def __str__(self):
        return f'EarnTxn({self.customer.code}: +{self.points_earned} [{self.source}])'


class BonusEvent(models.Model):
    """
    Manual or automated bonus points award record।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='bonus_events',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='bonus_events',
        verbose_name='Customer',
    )

    points = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Bonus Points')
    reason = models.CharField(max_length=500, verbose_name='Reason')
    triggered_by = models.CharField(max_length=200, null=True, blank=True, verbose_name='Triggered By')

    # Campaign/offer link
    campaign = models.ForeignKey(
        'djoyalty.LoyaltyCampaign',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='bonus_awards',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Bonus Event'
        verbose_name_plural = 'Bonus Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
        ]

    def __str__(self):
        return f'BonusEvent({self.customer.code}: {self.points} -- {self.reason[:50]})'


class EarnRuleLog(models.Model):
    """
    Audit log for earn rule triggers।
    """
    rule = models.ForeignKey(
        EarnRule,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='Earn Rule',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='earn_rule_logs',
    )
    triggered_at = models.DateTimeField(default=timezone.now)
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    reason = models.CharField(max_length=500, null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Earn Rule Log'
        # AUDIT FIX (4): (customer, triggered_at) for customer earn history;
        # (rule, triggered_at) for rule analytics; (customer, success) for
        # troubleshooting failed earn events.
        indexes = [
            models.Index(fields=['customer', 'triggered_at'],
                         name='earnlog_customer_time_idx'),
            models.Index(fields=['rule', 'triggered_at'],
                         name='earnlog_rule_time_idx'),
            models.Index(fields=['customer', 'success'],
                         name='earnlog_customer_success_idx'),
        ]
        verbose_name_plural = 'Earn Rule Logs'
        ordering = ['-triggered_at']

    def __str__(self):
        return f'EarnLog({self.rule.name} -> {self.customer.code}: {self.points_awarded})'
