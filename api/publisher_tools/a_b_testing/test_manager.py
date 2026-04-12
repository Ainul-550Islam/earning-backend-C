# api/publisher_tools/a_b_testing/test_manager.py
"""
A/B Test Manager — Full A/B testing system।
Floor price, ad format, placement, waterfall tests support করে।
"""
import uuid
import math
from decimal import Decimal
from typing import List, Dict, Optional
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import TimeStampedModel


# ──────────────────────────────────────────────────────────────────────────────
# A/B TEST MODELS
# ──────────────────────────────────────────────────────────────────────────────

class ABTest(TimeStampedModel):
    """
    A/B Test — একটি experiment-এর সম্পূর্ণ definition।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_abtest_tenant',
        db_index=True,
    )

    STATUS_CHOICES = [
        ('draft',     _('Draft')),
        ('running',   _('Running')),
        ('paused',    _('Paused')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]

    TYPE_CHOICES = [
        ('placement',   _('Placement Test')),
        ('ad_format',   _('Ad Format Test')),
        ('floor_price', _('Floor Price Test')),
        ('waterfall',   _('Waterfall Test')),
        ('creative',    _('Creative Test')),
        ('multivariate',_('Multivariate Test')),
    ]

    WINNER_REASON_CHOICES = [
        ('highest_revenue', _('Highest Revenue')),
        ('highest_ecpm',    _('Highest eCPM')),
        ('highest_fill',    _('Highest Fill Rate')),
        ('highest_ctr',     _('Highest CTR')),
        ('statistical_sig', _('Statistical Significance')),
        ('manual',          _('Manual Selection')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='ab_tests',
        verbose_name=_("Publisher"),
    )
    ad_unit = models.ForeignKey(
        'publisher_tools.AdUnit',
        on_delete=models.CASCADE,
        related_name='ab_tests',
        verbose_name=_("Ad Unit"),
    )
    test_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_("Test ID"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Test Name"))
    hypothesis = models.TextField(
        blank=True,
        verbose_name=_("Hypothesis"),
        help_text=_("এই test-এর hypothesis কী?"),
    )
    test_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name=_("Test Type"),
        db_index=True,
    )

    # ── Status & Timing ───────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name=_("Status"),
        db_index=True,
    )
    start_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Start Date"))
    end_date   = models.DateTimeField(null=True, blank=True, verbose_name=_("End Date"))
    min_duration_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1)],
        verbose_name=_("Minimum Duration (days)"),
    )

    # ── Statistical Settings ──────────────────────────────────────────────────
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00'),
        verbose_name=_("Required Confidence Level (%)"),
    )
    min_sample_size = models.IntegerField(
        default=1000,
        verbose_name=_("Min Sample Size per Variant"),
    )

    # ── Results ───────────────────────────────────────────────────────────────
    winner_variant = models.ForeignKey(
        'ABTestVariant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_tests',
        verbose_name=_("Winner Variant"),
    )
    winner_reason = models.CharField(
        max_length=30,
        choices=WINNER_REASON_CHOICES,
        blank=True,
        verbose_name=_("Winner Reason"),
    )
    confidence_achieved = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        verbose_name=_("Confidence Achieved (%)"),
    )
    statistical_significance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        verbose_name=_("Statistical Significance (%)"),
    )
    concluded_at = models.DateTimeField(null=True, blank=True)

    # ── Notes ─────────────────────────────────────────────────────────────────
    description = models.TextField(blank=True)
    conclusion_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_ab_tests'
        verbose_name = _('A/B Test')
        verbose_name_plural = _('A/B Tests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'status']),
            models.Index(fields=['ad_unit', 'status']),
            models.Index(fields=['test_type']),
        ]

    def __str__(self):
        return f"{self.test_id} — {self.name} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.test_id:
            count = ABTest.objects.count() + 1
            self.test_id = f"TEST{count:06d}"
        super().save(*args, **kwargs)

    @property
    def is_running(self):
        return self.status == 'running'

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        elif self.start_date:
            return (timezone.now() - self.start_date).days
        return 0

    @property
    def has_winner(self):
        return self.winner_variant is not None

    def can_declare_winner(self) -> bool:
        """Winner declare করা যাবে কিনা চেক করে"""
        if self.status != 'running':
            return False
        if self.duration_days < self.min_duration_days:
            return False
        # Check if any variant has enough samples
        sufficient_data = self.variants.filter(
            total_impressions__gte=self.min_sample_size
        ).count()
        return sufficient_data >= 2

    @transaction.atomic
    def start(self):
        """Test শুরু করে"""
        if self.status != 'draft':
            raise ValueError(f'Cannot start test in {self.status} status.')
        if self.variants.count() < 2:
            raise ValueError('At least 2 variants required to start a test.')
        self.status = 'running'
        self.start_date = timezone.now()
        self.save(update_fields=['status', 'start_date', 'updated_at'])

    @transaction.atomic
    def pause(self):
        """Test pause করে"""
        if self.status != 'running':
            raise ValueError('Only running tests can be paused.')
        self.status = 'paused'
        self.save(update_fields=['status', 'updated_at'])

    @transaction.atomic
    def resume(self):
        """Paused test resume করে"""
        if self.status != 'paused':
            raise ValueError('Only paused tests can be resumed.')
        self.status = 'running'
        self.save(update_fields=['status', 'updated_at'])

    @transaction.atomic
    def declare_winner(self, variant, reason: str = 'statistical_sig', notes: str = ''):
        """Winner declare করে এবং test complete করে"""
        if not self.can_declare_winner():
            raise ValueError('Cannot declare winner: insufficient data or test not running.')

        self.winner_variant  = variant
        self.winner_reason   = reason
        self.concluded_at    = timezone.now()
        self.conclusion_notes = notes
        self.status          = 'completed'
        self.end_date        = timezone.now()
        self.save()

    @transaction.atomic
    def auto_declare_winner(self):
        """Statistical significance-এর ভিত্তিতে auto winner declare করে"""
        if not self.can_declare_winner():
            return None

        variants = self.variants.filter(total_impressions__gte=self.min_sample_size)
        if variants.count() < 2:
            return None

        control = variants.order_by('created_at').first()
        best_variant = None
        best_confidence = 0

        for variant in variants:
            if variant == control:
                continue

            from ..utils import calculate_statistical_significance, calculate_uplift
            confidence = calculate_statistical_significance(
                control.total_impressions,
                int(control.total_revenue * 100),  # Proxy for conversions
                variant.total_impressions,
                int(variant.total_revenue * 100),
            )

            if confidence > best_confidence:
                best_confidence = confidence
                best_variant = variant

        self.confidence_achieved = Decimal(str(best_confidence))
        self.statistical_significance = Decimal(str(best_confidence))

        if best_confidence >= float(self.confidence_level) and best_variant:
            uplift = calculate_uplift(
                float(control.ecpm), float(best_variant.ecpm)
            ) if control.ecpm and best_variant.ecpm else 0

            if uplift > 0:
                self.declare_winner(
                    best_variant,
                    'statistical_sig',
                    f'Statistical confidence: {best_confidence:.1f}%, eCPM uplift: {uplift:.1f}%'
                )
                return best_variant

        self.save(update_fields=['confidence_achieved', 'statistical_significance', 'updated_at'])
        return None


class ABTestVariant(TimeStampedModel):
    """
    A/B Test-এর একটি Variant।
    Control (original) বা Treatment (new) হতে পারে।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_abtestvar_tenant',
        db_index=True,
    )

    # ── Core ──────────────────────────────────────────────────────────────────
    test = models.ForeignKey(
        ABTest,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name=_("Test"),
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Variant Name"),
        help_text=_("e.g., Control, Variant A, Variant B"),
    )
    is_control = models.BooleanField(
        default=False,
        verbose_name=_("Is Control"),
        help_text=_("True হলে এটা original/baseline variant"),
    )

    # ── Traffic Split ─────────────────────────────────────────────────────────
    traffic_split = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Traffic Split (%)"),
        help_text=_("মোট traffic-এর কত % এই variant-এ যাবে"),
    )

    # ── Configuration ─────────────────────────────────────────────────────────
    config = models.JSONField(
        default=dict,
        verbose_name=_("Variant Configuration"),
        help_text=_("Test type অনুযায়ী config: floor_price, format, position, etc."),
    )

    # ── Performance Metrics ───────────────────────────────────────────────────
    total_impressions = models.BigIntegerField(default=0, verbose_name=_("Impressions"))
    total_clicks      = models.BigIntegerField(default=0, verbose_name=_("Clicks"))
    total_revenue     = models.DecimalField(
        max_digits=14, decimal_places=6, default=Decimal('0.000000')
    )
    total_ad_requests = models.BigIntegerField(default=0)

    # ── Derived (stored for fast access) ─────────────────────────────────────
    ecpm      = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    ctr       = models.DecimalField(max_digits=6,  decimal_places=4, default=Decimal('0.0000'))
    fill_rate = models.DecimalField(max_digits=6,  decimal_places=4, default=Decimal('0.0000'))

    class Meta:
        db_table = 'publisher_tools_ab_test_variants'
        verbose_name = _('A/B Test Variant')
        verbose_name_plural = _('A/B Test Variants')
        ordering = ['test', 'is_control', 'name']
        indexes = [
            models.Index(fields=['test', 'is_control']),
        ]

    def __str__(self):
        ctrl = ' [CONTROL]' if self.is_control else ''
        return f"{self.test.test_id} — {self.name}{ctrl}"

    def update_metrics(self, impressions: int, clicks: int, revenue: Decimal, requests: int):
        """Variant metrics update করে"""
        self.total_impressions += impressions
        self.total_clicks      += clicks
        self.total_revenue     += revenue
        self.total_ad_requests += requests

        from ..utils import calculate_ecpm, calculate_ctr, calculate_fill_rate
        self.ecpm      = calculate_ecpm(self.total_revenue, self.total_impressions)
        self.ctr       = calculate_ctr(self.total_clicks, self.total_impressions)
        self.fill_rate = calculate_fill_rate(self.total_impressions, self.total_ad_requests)
        self.save()

    @property
    def revenue_per_impression(self):
        if self.total_impressions > 0:
            return self.total_revenue / self.total_impressions
        return Decimal('0')


# ──────────────────────────────────────────────────────────────────────────────
# A/B TEST SERVICE FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def create_floor_price_test(
    publisher,
    ad_unit,
    control_floor: Decimal,
    test_floor: Decimal,
    name: str = None,
) -> ABTest:
    """
    Floor price A/B test তৈরি করে।
    control_floor: existing floor price
    test_floor: new floor price to test
    """
    test = ABTest.objects.create(
        publisher=publisher,
        ad_unit=ad_unit,
        name=name or f'Floor Price Test: ${control_floor} vs ${test_floor}',
        test_type='floor_price',
        hypothesis=f'Increasing floor price from ${control_floor} to ${test_floor} will increase eCPM without significantly reducing fill rate.',
        confidence_level=Decimal('95.00'),
        min_sample_size=1000,
    )

    # Control variant
    ABTestVariant.objects.create(
        test=test,
        name='Control (Original)',
        is_control=True,
        traffic_split=Decimal('50.00'),
        config={'floor_price': float(control_floor)},
    )

    # Test variant
    ABTestVariant.objects.create(
        test=test,
        name='Variant A (New Floor)',
        is_control=False,
        traffic_split=Decimal('50.00'),
        config={'floor_price': float(test_floor)},
    )

    return test


def create_placement_test(
    publisher,
    ad_unit,
    positions: List[str],
    name: str = None,
) -> ABTest:
    """
    Ad placement position test তৈরি করে।
    positions: ['above_fold', 'in_content', 'sticky_bottom']
    """
    if len(positions) < 2:
        raise ValueError('At least 2 positions required for placement test.')

    test = ABTest.objects.create(
        publisher=publisher,
        ad_unit=ad_unit,
        name=name or f'Placement Test: {" vs ".join(positions[:3])}',
        test_type='placement',
        hypothesis='Testing optimal ad placement position for maximum revenue.',
        confidence_level=Decimal('95.00'),
        min_sample_size=1000,
    )

    split = Decimal(str(round(100 / len(positions), 2)))
    for i, position in enumerate(positions):
        ABTestVariant.objects.create(
            test=test,
            name=f'Position: {position}',
            is_control=(i == 0),
            traffic_split=split,
            config={'position': position},
        )

    return test


def get_test_results(test: ABTest) -> Dict:
    """
    Test-এর current results return করে।
    Statistical analysis সহ।
    """
    variants = test.variants.all()
    control = variants.filter(is_control=True).first()

    results = []
    for variant in variants:
        variant_data = {
            'id': str(variant.id),
            'name': variant.name,
            'is_control': variant.is_control,
            'traffic_split': float(variant.traffic_split),
            'total_impressions': variant.total_impressions,
            'total_clicks': variant.total_clicks,
            'total_revenue': float(variant.total_revenue),
            'ecpm': float(variant.ecpm),
            'ctr': float(variant.ctr),
            'fill_rate': float(variant.fill_rate),
        }

        if control and not variant.is_control and variant.total_impressions > 0:
            from ..utils import calculate_statistical_significance, calculate_uplift
            confidence = calculate_statistical_significance(
                control.total_impressions,
                int(float(control.total_revenue) * 1000),
                variant.total_impressions,
                int(float(variant.total_revenue) * 1000),
            )
            uplift = calculate_uplift(float(control.ecpm), float(variant.ecpm))
            variant_data['confidence'] = confidence
            variant_data['ecpm_uplift_pct'] = uplift
            variant_data['is_significant'] = confidence >= float(test.confidence_level)
        else:
            variant_data['confidence'] = None
            variant_data['ecpm_uplift_pct'] = None
            variant_data['is_significant'] = None

        results.append(variant_data)

    return {
        'test_id': test.test_id,
        'name': test.name,
        'status': test.status,
        'duration_days': test.duration_days,
        'can_declare_winner': test.can_declare_winner(),
        'has_winner': test.has_winner,
        'winner': str(test.winner_variant.id) if test.winner_variant else None,
        'variants': results,
        'confidence_level': float(test.confidence_level),
    }
