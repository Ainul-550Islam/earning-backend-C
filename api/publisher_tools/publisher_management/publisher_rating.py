# api/publisher_tools/publisher_management/publisher_rating.py
"""Publisher Rating System — Ratings from advertisers & automated quality scores।"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.models import TimeStampedModel


class PublisherRatingConfig(TimeStampedModel):
    """Rating system configuration।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_ratingconfig_tenant', db_index=True)
    min_rating_value     = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('1.0'))
    max_rating_value     = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('5.0'))
    weight_traffic       = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.35'))
    weight_content       = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.30'))
    weight_compliance    = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.25'))
    weight_communication = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.10'))
    is_active            = models.BooleanField(default=True)

    class Meta:
        db_table = 'publisher_tools_rating_configs'
        verbose_name = _('Rating Config')


class PublisherRatingRecord(TimeStampedModel):
    """Publisher rating record। Advertisers দেয় এই rating।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_ratingrecord_tenant', db_index=True)
    RATING_SOURCE_CHOICES = [
        ('advertiser',  _('Advertiser')),
        ('admin',       _('Admin Review')),
        ('automated',   _('Automated Score')),
        ('self',        _('Self Assessment')),
    ]
    publisher                = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='rating_records', db_index=True)
    rating_source            = models.CharField(max_length=20, choices=RATING_SOURCE_CHOICES, default='advertiser', db_index=True)
    rated_by_tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='ratings_given')
    overall_rating           = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))])
    traffic_quality_rating   = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('5.0'), validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))])
    content_quality_rating   = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('5.0'), validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))])
    compliance_rating        = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('5.0'), validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))])
    communication_rating     = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('5.0'), validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('5.0'))])
    review_title             = models.CharField(max_length=200, blank=True)
    review_text              = models.TextField(blank=True)
    is_verified_purchase     = models.BooleanField(default=False)
    is_public                = models.BooleanField(default=True)
    is_approved              = models.BooleanField(default=False)
    publisher_response       = models.TextField(blank=True)
    response_at              = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_rating_records'
        verbose_name = _('Publisher Rating Record')
        verbose_name_plural = _('Publisher Rating Records')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'rating_source'], name='idx_publisher_rating_sourc_8e3'),
            models.Index(fields=['overall_rating'], name='idx_overall_rating_1630'),
            models.Index(fields=['is_public', 'is_approved'], name='idx_is_public_is_approved_1631'),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.overall_rating}/5 ({self.rating_source})"

    @property
    def weighted_score(self):
        return (
            float(self.traffic_quality_rating) * 0.35 +
            float(self.content_quality_rating) * 0.30 +
            float(self.compliance_rating) * 0.25 +
            float(self.communication_rating) * 0.10
        )

    def respond(self, response_text: str):
        self.publisher_response = response_text
        self.response_at = timezone.now()
        self.save(update_fields=['publisher_response', 'response_at', 'updated_at'])


class PublisherAggregateRating(TimeStampedModel):
    """Publisher-এর aggregate/average rating।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_aggrrating_tenant', db_index=True)
    publisher          = models.OneToOneField('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='aggregate_rating')
    overall_avg        = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    traffic_avg        = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    content_avg        = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    compliance_avg     = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    communication_avg  = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    total_ratings      = models.IntegerField(default=0)
    five_star_count    = models.IntegerField(default=0)
    four_star_count    = models.IntegerField(default=0)
    three_star_count   = models.IntegerField(default=0)
    two_star_count     = models.IntegerField(default=0)
    one_star_count     = models.IntegerField(default=0)
    last_recalculated  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_aggregate_ratings'
        verbose_name = _('Publisher Aggregate Rating')

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.overall_avg}/5 ({self.total_ratings} reviews)"

    def recalculate(self):
        from django.db.models import Avg, Count, Q
        records = PublisherRatingRecord.objects.filter(publisher=self.publisher, is_approved=True)
        agg = records.aggregate(
            overall=Avg('overall_rating'), traffic=Avg('traffic_quality_rating'),
            content=Avg('content_quality_rating'), compliance=Avg('compliance_rating'),
            comm=Avg('communication_rating'), count=Count('id'),
        )
        self.overall_avg       = Decimal(str(round(agg.get('overall') or 0, 2)))
        self.traffic_avg       = Decimal(str(round(agg.get('traffic') or 0, 2)))
        self.content_avg       = Decimal(str(round(agg.get('content') or 0, 2)))
        self.compliance_avg    = Decimal(str(round(agg.get('compliance') or 0, 2)))
        self.communication_avg = Decimal(str(round(agg.get('comm') or 0, 2)))
        self.total_ratings     = agg.get('count') or 0
        for star in (5, 4, 3, 2, 1):
            count = records.filter(overall_rating__gte=star, overall_rating__lt=star+1).count()
            setattr(self, f'{["one","two","three","four","five"][star-1]}_star_count', count)
        self.last_recalculated = timezone.now()
        self.save()
