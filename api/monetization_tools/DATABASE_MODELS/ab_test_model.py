"""
DATABASE_MODELS/ab_test_model.py
==================================
QuerySet + Manager for ABTest, ABTestAssignment, FloorPriceConfig.
"""
from __future__ import annotations
import hashlib
from decimal import Decimal

from django.db import models
from django.db.models import Count, DecimalField, F, Q, Sum
from django.utils import timezone


class ABTestQuerySet(models.QuerySet):

    def running(self):
        return self.filter(status='running')

    def completed(self):
        return self.filter(status='completed')

    def draft(self):
        return self.filter(status='draft')

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def with_assignment_counts(self):
        return self.annotate(
            total_assignments=Count('monetization_tools_abtestassignment_test'),
            conversions=Count(
                'monetization_tools_abtestassignment_test',
                filter=Q(monetization_tools_abtestassignment_test__converted=True),
            ),
        )

    def active_for_unit(self, ad_unit_id):
        """Return running tests that involve this ad_unit in their variants."""
        tests = self.running()
        result = []
        for test in tests:
            variants = test.variants or []
            if any(str(v.get('ad_unit_id')) == str(ad_unit_id) for v in variants):
                result.append(test)
        return result


class ABTestManager(models.Manager):
    def get_queryset(self):
        return ABTestQuerySet(self.model, using=self._db)

    def running(self):
        return self.get_queryset().running()

    def for_tenant(self, tenant):
        return self.get_queryset().for_tenant(tenant).running()

    def with_stats(self):
        return self.get_queryset().with_assignment_counts()


class ABTestAssignmentQuerySet(models.QuerySet):

    def for_test(self, test_id):
        return self.filter(test_id=test_id)

    def for_user(self, user):
        return self.filter(user=user)

    def converted(self):
        return self.filter(converted=True)

    def by_variant(self, variant_name: str):
        return self.filter(variant_name=variant_name)

    def conversion_rate_by_variant(self, test_id):
        return (
            self.for_test(test_id)
                .values('variant_name')
                .annotate(
                    assigned=Count('id'),
                    converted=Count('id', filter=Q(converted=True)),
                )
                .order_by('variant_name')
        )


class ABTestAssignmentManager(models.Manager):
    def get_queryset(self):
        return ABTestAssignmentQuerySet(self.model, using=self._db)

    def get_or_assign(self, test, user) -> tuple:
        """
        Get existing assignment or create new one.
        Uses consistent hashing for deterministic bucketing.
        Returns (assignment, created).
        """
        existing = self.get_queryset().for_test(test.id).for_user(user).first()
        if existing:
            return existing, False

        # Deterministic bucket via SHA-256 of (test_id + user_id)
        hash_input = f"{test.test_id}{user.id}".encode()
        hash_int   = int(hashlib.sha256(hash_input).hexdigest(), 16)
        bucket     = hash_int % 100  # 0–99

        # Check traffic split gate
        if bucket >= test.traffic_split:
            return None, False

        # Assign to variant by weight
        variants = test.variants or []
        if not variants:
            return None, False

        total_weight = sum(v.get('weight', 0) for v in variants)
        if not total_weight:
            return None, False

        threshold = (bucket / test.traffic_split) * total_weight
        cumulative = 0
        assigned_variant = variants[-1]['name']
        for v in variants:
            cumulative += v.get('weight', 0)
            if threshold < cumulative:
                assigned_variant = v['name']
                break

        assignment, created = self.get_or_create(
            test=test,
            user=user,
            defaults={'variant_name': assigned_variant},
        )
        return assignment, created

    def conversion_stats(self, test_id):
        return self.get_queryset().conversion_rate_by_variant(test_id)


class FloorPriceConfigQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def for_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def for_country(self, country: str):
        return self.filter(Q(country=country.upper()) | Q(country__isnull=True) | Q(country=''))

    def for_device(self, device_type: str):
        return self.filter(
            Q(device_type=device_type.lower()) | Q(device_type__isnull=True) | Q(device_type='')
        )

    def most_specific(self, network_id, ad_unit_id=None, country=None, device_type=None, ad_format=None):
        """
        Return the most specific matching floor price config.
        Specificity order: (network+unit+country+device+format) > … > (network only)
        """
        qs = self.active().for_network(network_id)
        if ad_unit_id:
            qs = qs.filter(Q(ad_unit_id=ad_unit_id) | Q(ad_unit__isnull=True))
        if country:
            qs = qs.for_country(country)
        if device_type:
            qs = qs.for_device(device_type)
        if ad_format:
            qs = qs.filter(Q(ad_format=ad_format) | Q(ad_format__isnull=True) | Q(ad_format=''))
        return qs.order_by('-floor_ecpm').first()


class FloorPriceConfigManager(models.Manager):
    def get_queryset(self):
        return FloorPriceConfigQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def get_floor(self, network_id, ad_unit_id=None, country=None,
                  device_type=None, ad_format=None) -> Decimal:
        """Return the effective floor eCPM for given context. Falls back to 0."""
        config = self.get_queryset().most_specific(
            network_id, ad_unit_id, country, device_type, ad_format
        )
        return config.floor_ecpm if config else Decimal('0.0000')
